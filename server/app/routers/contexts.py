import copy

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..config import CONTRACT_VERSION
from ..models import REGISTRY
from ..storage import new_id

router = APIRouter(prefix="/api/m3", tags=["m3"])

ALKALI_TITRATION_TEMPLATE = {
    "schema_version": CONTRACT_VERSION,
    "name": "HCl 标定与碱灰总碱度（GB/T 601-2016 无水碳酸钠法）",
    "purpose": "以基准无水碳酸钠标定 HCl 浓度，测定碱灰总碱度（以 Na₂O 计），检查平行测定精密度",
    "model": "titration_standardization",
    "model_params": {
        "molar_mass_na2co3_g_mol": 105.99,   # GB/T 601-2016：M(½Na₂CO₃) = 52.994
        "molar_mass_na2o_g_mol": 61.979,
        "stock_volume_ml": 250,              # 碱灰试液定容体积
        "aliquot_volume_ml": 25,             # 每次滴定移取试液体积
    },
    "variables": {
        "columns": [
            {"key": "m", "role": "mass", "unit": "g"},                       # 标定行：基准 Na₂CO₃ 质量
            {"key": "V", "role": "volume", "unit": "mL"},                    # 标定/测定行：HCl 滴定体积
            {"key": "ms", "role": "sample_mass", "unit": "g", "optional": True},  # 测定行：碱灰试样质量
        ]
    },
    "reference": {
        "datasets": [],
        "crm": None,
        "limits": [{"label": "纯 Na₂CO₃ 理论总碱度（以 Na₂O 计）", "value": 58.47,
                    "unit": "%", "operator": "<="}],
    },
    "qc_rules": [
        {"rule_id": "standardization_rpad", "params": {"max": 0.002},
         "citation": "GB/T 601-2016 / 分析化学实验教学要求（相对平均偏差 ≤0.2%）"},
        {"rule_id": "parallel_rpd", "params": {"max": 0.002},
         "citation": "分析化学实验平行测定要求（相对平均偏差 ≤0.2%）"},
        {"rule_id": "outlier_grubbs", "params": {"alpha": 0.05}, "citation": "GB/T 4883"},
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
    "tpl_alkali_titration": {"status": "演示", "template": ALKALI_TITRATION_TEMPLATE},
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
