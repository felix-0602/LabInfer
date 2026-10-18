import io

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from ..config import CONTRACT_VERSION

router = APIRouter(prefix="/api/m7", tags=["m7"])


class ExportRequest(BaseModel):
    context_id: str
    format: str = "md"
    include: dict = {}


def _sections(ctx: dict, analysis: dict, findings: list[dict]):
    if analysis.get("model") == "titration_standardization":
        yield from _titration_sections(ctx, analysis, findings)
        return
    fit = analysis["fits"][0]
    yield ("h1", f"{ctx['name']} · 结果与讨论")
    yield ("p", f"实验目的：{ctx['purpose']}")
    yield ("h2", "标准曲线")
    yield ("p", f"线性回归 A = {fit['slope']}·c + {fit['intercept']}，"
                f"R² = {fit['r2']}（n = {fit['n']}）。")
    yield ("h2", "样品测定结果")
    yield ("table", [("样品", "浓度 (mg/L)", "U95", "报告值 (mg/L)")] + [
        (p["point_id"], str(p["value"]), str(p["u95"]), str(p["as_reported"]))
        for p in analysis.get("predictions", [])
    ])
    yield ("h2", "质量控制")
    for qc in analysis.get("qc_results", []):
        mark = "通过" if qc["pass"] else "未通过"
        yield ("li", f"{qc['rule_id']}：{mark}（依据 {qc.get('citation', '')}）")
    yield ("h2", "结论")
    for f in findings:
        yield ("li", f["text"])
    yield ("h2", "参照来源")
    for ref in ctx.get("reference", {}).get("datasets", []):
        meta = ref.get("meta", {})
        yield ("li", f"文献曲线：{meta.get('doi', '')} {meta.get('figure', '')}")
    crm = ctx.get("reference", {}).get("crm")
    if crm:
        yield ("li", f"质控样：{crm['id']}（{crm['value']}±{crm['u95']} mg/L）")
    for lim in ctx.get("reference", {}).get("limits", []):
        yield ("li", f"限值：{lim['label']} = {lim['value']} {lim.get('unit', '')}")


def _titration_sections(ctx: dict, analysis: dict, findings: list[dict]):
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
    yield ("h2", "质量控制")
    for qc in analysis.get("qc_results", []):
        mark = "通过" if qc["pass"] else "未通过"
        yield ("li", f"{qc['rule_id']}：{mark}（依据 {qc.get('citation', '')}）")
    yield ("h2", "结论")
    for f in findings:
        yield ("li", f["text"])
    yield ("h2", "参照来源")
    yield ("li", f"标定方法：GB/T 601-2016（基准无水碳酸钠 270~300 ℃ 灼烧至恒重，"
                 f"M(½Na₂CO₃) = 52.994 g/mol）")
    yield ("li", f"理论参照：纯 Na₂CO₃ 总碱度（以 Na₂O 计）= M(Na₂O)/M(Na₂CO₃) = "
                 f"{d['molar_mass_na2o']}/{d['molar_mass_na2co3']} ≈ 58.47%")
    yield ("li", "离群检验：GB/T 4883（格拉布斯）")
    for lim in ctx.get("reference", {}).get("limits", []):
        yield ("li", f"限值：{lim['label']} = {lim['value']} {lim.get('unit', '')}")


def _md(ctx: dict, analysis: dict, findings: list[dict]) -> str:
    lines = []
    for kind, content in _sections(ctx, analysis, findings):
        if kind == "h1":
            lines += [f"# {content}", ""]
        elif kind == "h2":
            lines += [f"## {content}", ""]
        elif kind == "p":
            lines += [content, ""]
        elif kind == "li":
            lines.append(f"- {content}")
        elif kind == "table":
            lines += ["| " + " | ".join(content[0]) + " |",
                      "| " + " | ".join("---" for _ in content[0]) + " |"]
            lines += ["| " + " | ".join(row) + " |" for row in content[1:]]
            lines.append("")
    return "\n".join(lines)


def _docx_bytes(ctx: dict, analysis: dict, findings: list[dict]) -> bytes:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.shared import Pt

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(11)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")

    for kind, content in _sections(ctx, analysis, findings):
        if kind == "h1":
            doc.add_heading(content, level=1)
        elif kind == "h2":
            doc.add_heading(content, level=2)
        elif kind == "p":
            doc.add_paragraph(content)
        elif kind == "li":
            doc.add_paragraph(content, style="List Bullet")
        elif kind == "table":
            table = doc.add_table(rows=len(content), cols=len(content[0]))
            for i, row in enumerate(content):
                for j, cell in enumerate(row):
                    table.rows[i].cells[j].text = cell
    buf = io.BytesIO()
    doc.save(buf)
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

    if body.format == "md":
        return PlainTextResponse(_md(ctx, analysis, findings), media_type="text/markdown")
    if body.format == "docx":
        data = _docx_bytes(ctx, analysis, findings)
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{body.context_id}.docx"'})
    return JSONResponse(status_code=422, content={
        "error": {"code": "FORMAT_PENDING", "message": f"格式待实现: {body.format}", "detail": {}}})
