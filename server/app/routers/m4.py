from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..services.analyze import analyze

router = APIRouter(prefix="/api/m4", tags=["m4"])


class AnalyzeRequest(BaseModel):
    context_id: str


@router.post("/analyze")
def run_analyze(body: AnalyzeRequest, request: Request):
    store = request.app.state.store
    ctx = store.get_context(body.context_id)
    if ctx is None:
        return JSONResponse(status_code=404, content={
            "error": {"code": "NOT_FOUND", "message": f"context 不存在: {body.context_id}", "detail": {}}})
    mine_id = ctx.get("datasets", {}).get("mine")
    if not mine_id:
        return JSONResponse(status_code=422, content={
            "error": {"code": "MISSING_DATASET", "message": "上下文尚未绑定我的数据集", "detail": {}}})
    mine = store.get_dataset(mine_id)
    if mine is None:
        return JSONResponse(status_code=404, content={
            "error": {"code": "NOT_FOUND", "message": f"dataset 不存在: {mine_id}", "detail": {}}})

    ref_datasets = {}
    for ref in ctx.get("reference", {}).get("datasets", []):
        ds = store.get_dataset(ref["dataset_id"])
        if ds is not None:
            ref_datasets[ref["dataset_id"]] = ds

    try:
        result = analyze(ctx, mine, ref_datasets)
    except ValueError as e:
        return JSONResponse(status_code=422, content={
            "error": {"code": "ANALYSIS_FAILED", "message": str(e), "detail": {}}})
    store.put_analysis(ctx["id"], result)
    return result
