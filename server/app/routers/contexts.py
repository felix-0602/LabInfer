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


def _all_templates(request: Request) -> list[tuple[str, dict]]:
    """内置模板 + 模板库（组织知识层，见 docs/wiki.md）。内置优先，库中 id 不得与内置冲突。"""
    items = [{"status": meta["status"], "template": dict(meta["template"], id=tid)}
             for tid, meta in TEMPLATES.items()]
    items += [{"status": t.get("status", "自定义"), "template": t}
              for t in request.app.state.store.list_templates()
              if t.get("id") and t["id"] not in TEMPLATES]
    return items


@router.get("/templates")
def list_templates(request: Request):
    out = []
    for item in _all_templates(request):
        t = item["template"]
        m = REGISTRY[t["model"]]
        out.append({
            "id": t["id"],
            "name": t["name"],
            "model": t["model"],
            "required_roles": [m.x_role, m.y_role],
            "formula": m.formula,
            "reference_preview": {
                "n_datasets": len(t.get("reference", {}).get("datasets", [])),
                "crm": t.get("reference", {}).get("crm"),
                "limits": t.get("reference", {}).get("limits", []),
            },
            "status": item["status"],
        })
    return out


@router.post("/templates", status_code=201)
def create_template(request: Request, body: dict):
    """把一次实验的骨架沉淀为可复用模板（wiki 层）。模板不含 datasets。"""
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={
            "error": {"code": "BAD_REQUEST", "message": "模板需要是 JSON 对象", "detail": {}}})
    name = str(body.get("name") or "").strip()
    model_id = body.get("model")
    if not name or model_id not in REGISTRY:
        return JSONResponse(status_code=400, content={
            "error": {"code": "BAD_REQUEST",
                      "message": f"模板需要非空 name 与注册表内的 model（{sorted(REGISTRY)}）",
                      "detail": {}}})
    m = REGISTRY[model_id]
    columns = (body.get("variables") or {}).get("columns") or []
    roles = {c.get("role") for c in columns if isinstance(c, dict)}
    if not {m.x_role, m.y_role} <= roles:
        return JSONResponse(status_code=400, content={
            "error": {"code": "BAD_REQUEST",
                      "message": f"variables.columns 缺少必需角色: {m.x_role}/{m.y_role}",
                      "detail": {}}})

    store = request.app.state.store
    tpl = copy.deepcopy(body)
    tpl.pop("datasets", None)
    tpl["id"] = tpl.get("id") or new_id("tpl")
    if tpl["id"] in TEMPLATES or store.get_template(tpl["id"]) is not None:
        return JSONResponse(status_code=409, content={
            "error": {"code": "CONFLICT", "message": f"模板 id 已存在: {tpl['id']}", "detail": {}}})
    tpl["schema_version"] = CONTRACT_VERSION
    tpl["status"] = "自定义"
    tpl.setdefault("model_params", {})
    tpl.setdefault("purpose", "")
    tpl.setdefault("reference", {"datasets": [], "crm": None, "limits": []})
    tpl.setdefault("qc_rules", [])
    return store.put_template(tpl)


@router.post("/contexts", status_code=201)
def create_context(body: CreateContext, request: Request):
    item = next((it for it in _all_templates(request)
                 if it["template"]["id"] == body.template_id), None)
    if item is None:
        return JSONResponse(status_code=404, content={
            "error": {"code": "NOT_FOUND", "message": f"模板不存在: {body.template_id}", "detail": {}}})
    ctx = copy.deepcopy(item["template"])
    ctx.pop("status", None)
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
