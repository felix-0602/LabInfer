from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from ..config import CONTRACT_VERSION

router = APIRouter(prefix="/api/m7", tags=["m7"])


class ExportRequest(BaseModel):
    context_id: str
    format: str = "md"
    include: dict = {}


def _md(ctx: dict, analysis: dict, findings: list[dict]) -> str:
    fit = analysis["fits"][0]
    lines = [
        f"# {ctx['name']} · 结果与讨论",
        "",
        f"**实验目的**：{ctx['purpose']}",
        "",
        "## 标准曲线",
        "",
        f"线性回归 A = {fit['slope']}·c + {fit['intercept']}，R² = {fit['r2']}（n = {fit['n']}）。",
        "",
        "## 样品测定结果",
        "",
        "| 样品 | 浓度 (mg/L) | 扩展不确定度 U95 | 报告值 (mg/L) |",
        "|---|---|---|---|",
    ]
    for p in analysis.get("predictions", []):
        lines.append(
            f"| {p['point_id']} | {p['value']} | {p['u95']} | {p['as_reported']} |")
    lines += ["", "## 质量控制", ""]
    for qc in analysis.get("qc_results", []):
        mark = "通过" if qc["pass"] else "**未通过**"
        lines.append(f"- {qc['rule_id']}：{mark}（依据 {qc.get('citation', '')}）")
    lines += ["", "## 结论", ""]
    for f in findings:
        lines.append(f"- {f['text']}")
    lines += ["", "## 参照来源", ""]
    for ref in ctx.get("reference", {}).get("datasets", []):
        meta = ref.get("meta", {})
        lines.append(f"- 文献曲线：{meta.get('doi', '')} {meta.get('figure', '')}")
    crm = ctx.get("reference", {}).get("crm")
    if crm:
        lines.append(f"- 质控样：{crm['id']}（{crm['value']}±{crm['u95']} mg/L）")
    for lim in ctx.get("reference", {}).get("limits", []):
        lines.append(f"- 限值：{lim['label']} = {lim['value']} mg/L")
    lines.append("")
    return "\n".join(lines)


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
    return JSONResponse(status_code=422, content={
        "error": {"code": "FORMAT_PENDING", "message": f"格式待实现: {body.format}", "detail": {}}})
