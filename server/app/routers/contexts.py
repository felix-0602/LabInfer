import copy

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..config import CONTRACT_VERSION
from ..models import REGISTRY
from ..storage import new_id

router = APIRouter(prefix="/api/m3", tags=["m3"])

AMMONIA_TEMPLATE = {
    "schema_version": CONTRACT_VERSION,
    "name": "水质氨氮检测（HJ 535-2009 纳氏试剂分光光度法）",
    "purpose": "测定水样氨氮浓度，判定是否达到 GB 3838-2002 III 类限值",
    "model": "linear_calibration",
    "model_params": {"final_volume_ml": 50},
    "variables": {
        "columns": [
            {"key": "c", "role": "concentration", "unit": "mg/L"},
            {"key": "A", "role": "signal", "unit": ""},
            {"key": "V", "role": "sample_volume", "unit": "mL", "optional": True, "default": 50},
            {"key": "dil", "role": "dilution_factor", "unit": "", "optional": True, "default": 1},
        ]
    },
    "reference": {
        "datasets": [],
        "crm": {"id": "GSB 07-3164-2014", "value": 0.716, "u95": 0.044, "unit": "mg/L"},
        "limits": [{"label": "GB 3838-2002 III 类", "value": 1.0, "unit": "mg/L", "operator": "<="}],
    },
    "qc_rules": [
        {"rule_id": "calibration_r2", "params": {"min": 0.999}, "citation": "HJ 535-2009"},
        {"rule_id": "parallel_rpd", "params": {"max": 0.10}, "citation": "HJ 630-2011"},
        {"rule_id": "outlier_grubbs", "params": {"alpha": 0.05}, "citation": "GB/T 4883"},
        {"rule_id": "crm_within_u95", "params": {}, "citation": "GSB 07-3164-2014 证书"},
    ],
}

IODINE_TEMPLATE = {
    "schema_version": CONTRACT_VERSION,
    "name": "碘钟反应动力学（过硫酸根-碘离子，规划中）",
    "purpose": "改变温度测变色时间，ln(1/t) 对 1/T 求 Arrhenius 活化能",
    "model": "arrhenius",
    "model_params": {},
    "variables": {
        "columns": [
            {"key": "T", "role": "temperature", "unit": "°C"},
            {"key": "t", "role": "time", "unit": "s"},
        ]
    },
    "reference": {"datasets": [], "crm": None, "limits": []},
    "qc_rules": [
        {"rule_id": "calibration_r2", "params": {"min": 0.99}, "citation": "教学惯例"},
        {"rule_id": "outlier_grubbs", "params": {"alpha": 0.05}, "citation": "GB/T 4883"},
    ],
}

TEMPLATES = {
    "tpl_ammonia_nessler": {"status": "演示", "template": AMMONIA_TEMPLATE},
    "tpl_iodine_clock": {"status": "规划", "template": IODINE_TEMPLATE},
}


class CreateContext(BaseModel):
    template_id: str


@router.get("/templates")
def list_templates():
    out = []
    for tid, item in TEMPLATES.items():
        t = item["template"]
        m = REGISTRY[t["model"]]
        out.append({
            "id": tid,
            "name": t["name"],
            "model": t["model"],
            "required_roles": [m.x_role, m.y_role],
            "formula": m.formula,
            "reference_preview": {
                "n_datasets": len(t["reference"]["datasets"]),
                "crm": t["reference"]["crm"],
                "limits": t["reference"]["limits"],
            },
            "status": item["status"],
        })
    return out


@router.post("/contexts", status_code=201)
def create_context(body: CreateContext, request: Request):
    item = TEMPLATES.get(body.template_id)
    if item is None:
        return JSONResponse(status_code=404, content={
            "error": {"code": "NOT_FOUND", "message": f"模板不存在: {body.template_id}", "detail": {}}})
    ctx = copy.deepcopy(item["template"])
    ctx["id"] = new_id("ctx")
    ctx["datasets"] = {"mine": None}
    return request.app.state.store.put_context(ctx)


@router.get("/contexts/{id}")
def get_context(id: str, request: Request):
    ctx = request.app.state.store.get_context(id)
    if ctx is None:
        return JSONResponse(status_code=404, content={
            "error": {"code": "NOT_FOUND", "message": f"context 不存在: {id}", "detail": {}}})
    return ctx


@router.put("/contexts/{id}")
def put_context(id: str, request: Request, body: dict):
    if not isinstance(body, dict) or "model" not in body:
        return JSONResponse(status_code=400, content={
            "error": {"code": "BAD_REQUEST", "message": "ExperimentContext 需要 model", "detail": {}}})
    body = copy.deepcopy(body)
    body["id"] = id
    return request.app.state.store.put_context(body)
