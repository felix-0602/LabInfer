import base64
import io
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from ..config import CONTRACT_VERSION

router = APIRouter(prefix="/api/m7", tags=["m7"])

_INCLUDE_KEYS = ("figure", "anomalies", "suggestions", "quality_control", "sources")
_TERM_MARK_RE = re.compile(r"\[([^\]]+)\]\((?:term:[a-z0-9_]+|num:[-+0-9.eE]+)\)")


def _plain_text(text: str) -> str:
    """报告是纯文字载体：Finding.text 里的 term/num 标记剥成显示文字（展开只在工作台里点）。"""
    return _TERM_MARK_RE.sub(r"\1", text)


class ExportRequest(BaseModel):
    context_id: str
    format: str = "md"
    include: dict = {}


def _flags(include: dict) -> dict:
    """include 勾选项，默认全开（contracts 0.7.0 M7 行）。"""
    return {k: bool(include.get(k, True)) for k in _INCLUDE_KEYS}


def _kept_findings(findings: list[dict], flags: dict) -> list[dict]:
    dropped = {"anomaly"} if not flags["anomalies"] else set()
    dropped |= {"suggestion"} if not flags["suggestions"] else set()
    return [f for f in findings if f.get("type") not in dropped]


def _titration_sections(ctx: dict, analysis: dict, findings: list[dict], flags: dict):
    fit = analysis["fits"][0]
    d = fit["derived"]
    yield ("h1", f"{ctx['name']} · 结果与讨论")
    yield ("p", f"实验目的：{ctx['purpose']}")
    yield ("h2", "HCl 标定")
    yield ("p", f"三份基准无水碳酸钠平行标定，c̄(HCl) = {d['c_hcl']} mol/L"
                f"（相对平均偏差 {round(d['rel_avg_dev_c'] * 100, 2)}%）；"
                f"滴定体积—称样量过原点拟合 R² = {fit['r2']}（n = {fit['n']}，"
                f"回归浓度 {d['c_regression']} mol/L）。")
    yield ("h2", "碱灰总碱度测定结果")
    yield ("table", [("平行", "V(HCl) (mL)", "w(Na₂O) (%)", "U95 (%)")] + [
        (p["point_id"], str(next(iter(p["input"].values()))), str(p["value"]), str(p["u95"]))
        for p in analysis.get("predictions", [])
    ])
    if d.get("w_na2o_mean_pct") is not None:
        yield ("p", f"平均总碱度（以 Na₂O 计）{round(d['w_na2o_mean_pct'], 2)}%，"
                    f"相对平均偏差 {round(d['rel_avg_dev_w'] * 100, 2)}%。")

    curve = analysis.get("titration_curve")
    if flags["figure"] and curve:
        yield ("h2", "滴定曲线")
        w = curve["indicator"]["dv_window_ml"]
        yield ("p", f"理论曲线（封闭体系）计量点 pH {curve['ph_eq']}；"
                    f"{curve['indicator']['name']} 变色窗 ΔV {w[0]}～{w[1]} mL"
                    f"（pH {curve['indicator']['ph_range'][0]}～{curve['indicator']['ph_range'][1]}）。")
        if curve["endpoints"]:
            rows = [(e["point_id"], f"{e['dv_ml']:+.3f}", str(e["ph"])) for e in curve["endpoints"]]
            yield ("table", [("平行", "ΔV (mL)", "pH")] + rows)
        yield ("image", "图 1 滴定曲线（蓝：理论；红点：各份终点）")

    if flags["quality_control"]:
        yield ("h2", "质量控制")
        for qc in analysis.get("qc_results", []):
            mark = "通过" if qc["pass"] else "未通过"
            yield ("li", f"{qc['rule_id']}：{mark}（依据 {qc.get('citation', '')}）")
    yield ("h2", "结论")
    for f in _kept_findings(findings, flags):
        yield ("li", _plain_text(f["text"]))
    if flags["sources"]:
        yield ("h2", "参照来源")
        yield ("li", f"标定方法：GB/T 601-2016（基准无水碳酸钠 270~300 ℃ 灼烧至恒重，"
                     f"M(½Na₂CO₃) = 52.994 g/mol）")
        yield ("li", f"理论参照：纯 Na₂CO₃ 总碱度（以 Na₂O 计）= M(Na₂O)/M(Na₂CO₃) = "
                     f"{d['molar_mass_na2o']}/{d['molar_mass_na2co3']} ≈ 58.47%")
        yield ("li", "离群检验：GB/T 4883（格拉布斯）")
        for lim in ctx.get("reference", {}).get("limits", []):
            yield ("li", f"限值：{lim['label']} = {lim['value']} {lim.get('unit', '')}")
        for ref in ctx.get("reference", {}).get("datasets", []):
            meta = ref.get("meta", {})
            yield ("li", f"文献曲线：{meta.get('doi', '')} {meta.get('figure', '')}")


def _sections(ctx: dict, analysis: dict, findings: list[dict], flags: dict):
    if analysis.get("model") == "titration_standardization":
        yield from _titration_sections(ctx, analysis, findings, flags)
        return
    fit = analysis["fits"][0]
    yield ("h1", f"{ctx['name']} · 结果与讨论")
    yield ("p", f"实验目的：{ctx['purpose']}")
    if flags["figure"]:
        yield ("h2", "标准曲线")
        yield ("p", f"线性回归 A = {fit['slope']}·c + {fit['intercept']}，"
                    f"R² = {fit['r2']}（n = {fit['n']}）。")
    yield ("h2", "样品测定结果")
    yield ("table", [("样品", "浓度 (mg/L)", "U95", "报告值 (mg/L)")] + [
        (p["point_id"], str(p["value"]), str(p["u95"]), str(p["as_reported"]))
        for p in analysis.get("predictions", [])
    ])
    if flags["quality_control"]:
        yield ("h2", "质量控制")
        for qc in analysis.get("qc_results", []):
            mark = "通过" if qc["pass"] else "未通过"
            yield ("li", f"{qc['rule_id']}：{mark}（依据 {qc.get('citation', '')}）")
    yield ("h2", "结论")
    for f in _kept_findings(findings, flags):
        yield ("li", _plain_text(f["text"]))
    if flags["sources"]:
        yield ("h2", "参照来源")
        for ref in ctx.get("reference", {}).get("datasets", []):
            meta = ref.get("meta", {})
            yield ("li", f"文献曲线：{meta.get('doi', '')} {meta.get('figure', '')}")
        crm = ctx.get("reference", {}).get("crm")
        if crm:
            yield ("li", f"质控样：{crm['id']}（{crm['value']}±{crm['u95']} mg/L）")
        for lim in ctx.get("reference", {}).get("limits", []):
            yield ("li", f"限值：{lim['label']} = {lim['value']} {lim.get('unit', '')}")


def _md(ctx: dict, analysis: dict, findings: list[dict], flags: dict,
        fig_uri: str = "figure.png") -> str:
    lines = []
    for kind, content in _sections(ctx, analysis, findings, flags):
        if kind == "h1":
            lines += [f"# {content}", ""]
        elif kind == "h2":
            lines += [f"## {content}", ""]
        elif kind == "p":
            lines += [content, ""]
        elif kind == "li":
            lines.append(f"- {content}")
        elif kind == "image":
            lines += [f"![{content}]({fig_uri})", ""]
        elif kind == "table":
            lines += ["| " + " | ".join(content[0]) + " |",
                      "| " + " | ".join("---" for _ in content[0]) + " |"]
            lines += ["| " + " | ".join(row) + " |" for row in content[1:]]
            lines.append("")
    return "\n".join(lines)


def _docx_bytes(ctx: dict, analysis: dict, findings: list[dict], flags: dict) -> bytes:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.shared import Pt

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(11)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")

    for kind, content in _sections(ctx, analysis, findings, flags):
        if kind == "h1":
            doc.add_heading(content, level=1)
        elif kind == "h2":
            doc.add_heading(content, level=2)
        elif kind == "p":
            doc.add_paragraph(content)
        elif kind == "li":
            doc.add_paragraph(content, style="List Bullet")
        elif kind == "image":
            doc.add_picture(io.BytesIO(_figure_png_bytes(ctx, analysis)), width=Pt(440))
            doc.add_paragraph(content)
        elif kind == "table":
            table = doc.add_table(rows=len(content), cols=len(content[0]))
            for i, row in enumerate(content):
                for j, cell in enumerate(row):
                    table.rows[i].cells[j].text = cell
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


_CJK_FONTS = ("Noto Sans CJK SC", "WenQuanYi Micro Hei", "WenQuanYi Zen Hei",
              "AR PL UMing CN", "WenQuanYi Zen Hei Mono")


def _apply_cjk_font() -> None:
    """图例与轴标签含中文（指示剂名、样品名等）。环境里有中文字体就用，
    免得画成豆腐块；一个都没有则维持 DejaVu 回退（届时图例只剩 ASCII 部分）。"""
    import matplotlib.font_manager as fm

    available = {f.name for f in fm.fontManager.ttflist}
    for name in _CJK_FONTS:
        if name in available:
            import matplotlib.pyplot as plt
            plt.rcParams["font.family"] = "sans-serif"
            plt.rcParams["font.sans-serif"] = [name, "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False   # 中文字体普遍缺 U+2212
            return


def _figure_png_bytes(ctx: dict, analysis: dict) -> bytes:
    """图 1：滴定曲线（有 titration_curve 时）或 V–m 散点拟合。
    图内中文（指示剂名等）依赖 _apply_cjk_font 找到的字体。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _apply_cjk_font()

    fig, ax = plt.subplots(figsize=(7.0, 4.2), dpi=150)
    curve = analysis.get("titration_curve")
    if curve:
        ax.plot([p["x"] for p in curve["theory"]], [p["y"] for p in curve["theory"]],
                color="#1e3bff", lw=2, label="theory (closed)")
        for lit in curve.get("literature", []):
            ax.plot([p["x"] for p in lit["points"]], [p["y"] for p in lit["points"]],
                    "--", color="#0a0b10", lw=1.2, label=f"literature {lit['dataset_id']}")
        w = curve["indicator"]["dv_window_ml"]
        ax.axvspan(w[0], w[1], color="#1e3bff", alpha=0.12,
                   label=f"indicator window {curve['indicator'].get('name', '')}")
        for ep in curve.get("endpoints", []):
            ax.plot(ep["dv_ml"], ep["ph"], "o", ms=6, color="#e5242b")
            ax.annotate(ep["point_id"], (ep["dv_ml"], ep["ph"]),
                        textcoords="offset points", xytext=(4, 4), fontsize=9)
        ax.axvline(0, color="#6b7180", lw=0.6, ls=":")
        ax.set_xlabel("delta V (mL)")
        ax.set_ylabel("pH")
    else:
        t = analysis["transformed"][0]
        fit = analysis["fits"][0]
        ax.plot([p["x"] for p in t["points"]], [p["y"] for p in t["points"]],
                "o", color="#1e3bff", ms=6, label="data")
        x0, x1 = min(p["x"] for p in t["points"]), max(p["x"] for p in t["points"])
        ax.plot([x0, x1], [fit["slope"] * x0, fit["slope"] * x1],
                color="#1e3bff", lw=1.5, label="fit through origin")
        ax.set_xlabel(f"{t['x_label']} ({t['x_unit']})")
        ax.set_ylabel(f"{t['y_label']} ({t['y_unit']})")
    ax.legend(fontsize=9, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title(f"LabInfer | {analysis['model']} | {analysis['context_id']}",
                 fontsize=9, color="#6b7180", loc="left")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


@router.post("/export")
def export(body: ExportRequest, request: Request):
    store = request.app.state.store
    ctx = store.get_context(body.context_id)
    if ctx is None:
        return JSONResponse(status_code=404, content={
            "error": {"code": "NOT_FOUND", "message": f"context 不存在: {body.context_id}", "detail": {}}})
    analysis = store.get_analysis(body.context_id)
    if analysis is None:
        return JSONResponse(status_code=422, content={
            "error": {"code": "NO_ANALYSIS", "message": "先调用 POST /api/m4/analyze", "detail": {}}})
    findings = store.get_findings(body.context_id) or []
    flags = _flags(body.include)

    if body.format == "md":
        # 图片内嵌为 data URI，导出的单个 md 文件自包含（figure.png 相对链接无文件可指）
        fig_uri = f"data:image/png;base64,{base64.b64encode(_figure_png_bytes(ctx, analysis)).decode()}" \
            if flags["figure"] else "figure.png"
        return PlainTextResponse(_md(ctx, analysis, findings, flags, fig_uri), media_type="text/markdown")
    if body.format == "docx":
        data = _docx_bytes(ctx, analysis, findings, flags)
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{body.context_id}.docx"'})
    if body.format == "png":
        if not flags["figure"]:
            return JSONResponse(status_code=422, content={
                "error": {"code": "BAD_REQUEST",
                          "message": "include.figure=false 时不导出图件", "detail": {}}})
        return StreamingResponse(
            io.BytesIO(_figure_png_bytes(ctx, analysis)), media_type="image/png",
            headers={"Content-Disposition": f'attachment; filename="{body.context_id}-figure1.png"'})
    return JSONResponse(status_code=422, content={
        "error": {"code": "FORMAT_PENDING", "message": f"格式待实现: {body.format}", "detail": {}}})
