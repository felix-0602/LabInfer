from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from ..cache import (cache_get, cache_put, is_demo_image, runtime_cache_put,
                     sha256_bytes)
from ..config import CONTRACT_VERSION
from ..llm import LlmError, llm_configured
from ..storage import new_id
from ..vlm import recognize_record

router = APIRouter(prefix="/api/m1", tags=["m1"])


@router.post("/records", status_code=201)
async def create_record(request: Request, image: UploadFile = File(...),
                        context_id: str = Form(...)):
    store = request.app.state.store
    ctx = store.get_context(context_id)
    if ctx is None:
        return JSONResponse(status_code=404, content={
            "error": {"code": "NOT_FOUND", "message": f"context 不存在: {context_id}", "detail": {}}})

    data = await image.read()
    suffix = Path(image.filename or "img").suffix[:8]
    path = store.save_upload(data, suffix)
    digest = sha256_bytes(data)

    cached = cache_get("m1", digest)
    if cached is not None:
        ds = cached
        ds.setdefault("cached", True)
    elif llm_configured():
        try:
            ds = await recognize_record(data, ctx)
        except (LlmError, ValueError) as e:
            return JSONResponse(status_code=503, content={
                "error": {"code": "VLM_UNAVAILABLE", "message": f"视觉识别失败: {e}", "detail": {}}})
        bake = dict(ds)
        if is_demo_image(digest):
            cache_put("m1", digest, bake)        # 白名单图：进入库的演示缓存
        else:
            runtime_cache_put("m1", digest, bake)  # 其余：运行时缓存（不入库）
    else:
        return JSONResponse(status_code=503, content={
            "error": {"code": "VLM_UNAVAILABLE",
                      "message": "视觉模型未配置且未命中演示缓存", "detail": {}}})

    ds.setdefault("schema_version", CONTRACT_VERSION)
    ds.setdefault("source", "my_experiment")
    ds.setdefault("meta", {})
    ds.setdefault("id", new_id("ds"))
    ds["meta"]["image_ref"] = str(path)
    store.put_dataset(ds)
    ctx["datasets"]["mine"] = ds["id"]
    store.put_context(ctx)
    return ds
