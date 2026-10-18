from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..config import CONTRACT_VERSION

router = APIRouter(prefix="/api/snapshot", tags=["demo"])


@router.get("/{context_id}")
def snapshot(context_id: str, request: Request):
    """演示保底快照：M8 构建时拉取存为影子文件，后端不可用时本地加载。"""
    store = request.app.state.store
    ctx = store.get_context(context_id)
    if ctx is None:
        return JSONResponse(status_code=404, content={
            "error": {"code": "NOT_FOUND", "message": f"context 不存在: {context_id}", "detail": {}}})
    analysis = store.get_analysis(context_id)
    if analysis is None:
        return JSONResponse(status_code=422, content={
            "error": {"code": "NO_ANALYSIS", "message": "先调用 POST /api/m4/analyze", "detail": {}}})

    dataset_ids = [ctx.get("datasets", {}).get("mine")]
    dataset_ids += [r["dataset_id"] for r in ctx.get("reference", {}).get("datasets", [])]
    datasets = [d for d in (store.get_dataset(i) for i in dataset_ids if i) if d is not None]

    return {
        "schema_version": CONTRACT_VERSION,
        "context": ctx,
        "datasets": datasets,
        "analysis": analysis,
        "findings": store.get_findings(context_id) or [],
    }
