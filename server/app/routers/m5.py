import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from ..llm import LlmError, llm_configured
from ..prompts import llm_findings
from ..services.findings import attach_ladder, compose_findings

router = APIRouter(prefix="/api/m5", tags=["m5"])


class FindingsRequest(BaseModel):
    context_id: str


@router.post("/findings")
async def findings(body: FindingsRequest, request: Request):
    store = request.app.state.store
    ctx = store.get_context(body.context_id)
    if ctx is None:
        return JSONResponse(status_code=404, content={
            "error": {"code": "NOT_FOUND", "message": f"context 不存在: {body.context_id}", "detail": {}}})
    analysis = store.get_analysis(ctx["id"])
    if analysis is None:
        return JSONResponse(status_code=422, content={
            "error": {"code": "NO_ANALYSIS",
                      "message": "先调用 POST /api/m4/analyze", "detail": {}}})
    mine = store.get_dataset(ctx["datasets"]["mine"])

    items = None
    if llm_configured():
        try:
            items, _dropped = await llm_findings(analysis, ctx, mine)
        except (LlmError, ValueError):
            items = None
    if not items:
        items = compose_findings(analysis, ctx, mine)
    items = attach_ladder(items, ctx, analysis)
    store.put_findings(ctx["id"], items)

    def gen():
        for f in items:
            yield f"event: finding\ndata: {json.dumps(f, ensure_ascii=False)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
