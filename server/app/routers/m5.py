import asyncio
import hashlib
import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from ..cache import runtime_cache_get, runtime_cache_put
from ..config import settings
from ..llm import LlmError, llm_configured
from ..prompts import llm_findings
from ..services.findings import attach_ladder, compose_findings

router = APIRouter(prefix="/api/m5", tags=["m5"])

# glm-5.3 推理可达数分钟。若等 LLM 完成才发首字节，公网链路上无字节的连接会被
# NAT/中间设备掐掉，浏览器 fetch 直接报「AI 解读连不上」（本地开发不经过公网
# 中间设备，测不出来）。改为：响应头立刻回，LLM 后台跑，SSE 注释行做心跳。
# `: ` 开头的行是 SSE 注释，前端解析器（web/src/api.ts streamFindings）不认它。
_KEEPALIVE_SECONDS = 10


class FindingsRequest(BaseModel):
    context_id: str


def _cache_key(ctx: dict, analysis: dict) -> str:
    # 结论缓存按 ctx+模型+分析结果哈希：重新 analyze 后 key 变化，自然失效
    payload = json.dumps({"ctx": ctx["id"], "model": settings.llm_model,
                          "analysis": analysis}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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

    key = _cache_key(ctx, analysis)

    async def gen():
        items = runtime_cache_get("m5", key)
        if items is None and llm_configured():
            task = asyncio.create_task(llm_findings(analysis, ctx, mine))
            # 客户端断开时生成器被取消，后台任务自行结束；异常就地取走避免告警
            task.add_done_callback(lambda t: t.cancelled() or t.exception())
            while not task.done():
                yield ": keepalive\n\n"
                await asyncio.wait({task}, timeout=_KEEPALIVE_SECONDS)
            try:
                items, _dropped = task.result()
            except (LlmError, ValueError):
                items = None
            if items:
                runtime_cache_put("m5", key, items)
        if not items:
            items = compose_findings(analysis, ctx, mine)
        items = attach_ladder(items, ctx, analysis)
        store.put_findings(ctx["id"], items)
        for f in items:
            yield f"event: finding\ndata: {json.dumps(f, ensure_ascii=False)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")

