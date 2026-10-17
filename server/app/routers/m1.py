from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from ..cache import cache_get, sha256_bytes
from ..config import CONTRACT_VERSION

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
    if cached is None:
        # VLM（glm-5.3-flash）接入点：识别手写记录为 Dataset。未接入或不可用即 503，
        # M8 引导用户手动录入（契约约定的兜底）。
        return JSONResponse(status_code=503, content={
            "error": {"code": "VLM_UNAVAILABLE",
                      "message": "视觉模型未接入或不可用，且未命中演示缓存", "detail": {}}})

    ds = cached
    ds.setdefault("schema_version", CONTRACT_VERSION)
    ds.setdefault("source", "my_experiment")
    ds.setdefault("meta", {})
    ds["meta"]["image_ref"] = str(path)
    ds.setdefault("cached", True)
    store.put_dataset(ds)
    ctx["datasets"]["mine"] = ds["id"]
    store.put_context(ctx)
    return ds
