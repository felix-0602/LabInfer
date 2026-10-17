import copy

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..config import CONTRACT_VERSION
from ..storage import new_id

router = APIRouter(prefix="/api/datasets", tags=["storage"])


def not_found(kind: str, id: str):
    return JSONResponse(status_code=404, content={
        "error": {"code": "NOT_FOUND", "message": f"{kind} 不存在: {id}", "detail": {}}})


@router.get("/{id}")
def get_dataset(id: str, request: Request):
    ds = request.app.state.store.get_dataset(id)
    if ds is None:
        return not_found("dataset", id)
    return ds


@router.put("/{id}")
def put_dataset(id: str, request: Request, body: dict):
    if not isinstance(body, dict) or "columns" not in body or "rows" not in body:
        return JSONResponse(status_code=400, content={
            "error": {"code": "BAD_REQUEST", "message": "Dataset 需要 columns 与 rows", "detail": {}}})
    body = copy.deepcopy(body)
    body["id"] = id
    body.setdefault("schema_version", CONTRACT_VERSION)
    body.setdefault("source", "my_experiment")
    body.setdefault("meta", {})
    return request.app.state.store.put_dataset(body)
