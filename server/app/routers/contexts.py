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
        # 0.7.0：滴定曲线与误差预算的常数（契约「滴定公式」节）
        "pka1": 6.35, "pka2": 10.33,         # 碳酸 25 ℃
        "initial_water_ml": 30,              # 溶解基准物的水量（教材 25～35 mL 取中值）
        "indicator": {"name": "甲基橙", "ph_range": [3.1, 4.4]},
        "balance_error_g": 0.0001,           # 单次称量最大误差，差减法计两次
        "burette_error_ml": 0.01,            # 单次读数最大误差，计两次
    },
    "ladder": {                              # 讲解阶梯，规则见 docs/wiki.md#讲解阶梯
        "base_level": 3,
        "rungs": [
            {"rung_id": "L3-formula", "level": 3, "title": "浓度与总碱度怎么算",
             "concept": "相对平均偏差的含义与代入公式计算 c、w",
             "anchor": {"type": "fit"}, "trigger": None,
             "source": "实验教材 实验 3 数据处理"},
            {"rung_id": "L4-indicator", "level": 4, "title": "为什么用甲基橙",
             "concept": "Na₂CO₃ 有两个化学计量点（约 pH 8.3 与 3.9），第二个落在甲基橙变色区内",
             "anchor": {"type": "comparison", "target": "titration_curve"}, "trigger": None,
             "source": "实验教材 实验目的 3；分析化学教材 酸碱滴定章"},
            {"rung_id": "L4-co2", "level": 4, "title": "为什么近终点要防 CO₂",
             "concept": "溶解的 CO₂ 形成缓冲，突跃变缓，终点提前",
             "anchor": {"type": "comparison", "target": "titration_curve"}, "trigger": None,
             "source": "分析化学教材；GB/T 601-2016 HCl 标定条（煮沸步骤，待核）"},
            {"rung_id": "L5-error-type", "level": 5, "title": "误差分系统与随机",
             "concept": "系统误差让三份同向偏移、拉动平均值；随机误差拉大离散。基准物吸水 1% 是系统误差（思考题 2）",
             "anchor": {"type": "comparison", "target": "vs_limit[0]"}, "trigger": None,
             "source": "实验教材 思考题 2"},
            {"rung_id": "L5-mass-range", "level": 5, "title": "为什么称样量 0.15～0.20 g、滴定体积 20 mL 以上",
             "concept": "天平两次称量 ±0.0002 g、滴定管两次读数 ±0.02 mL，各自控制在约 0.1% 以内",
             "anchor": {"type": "fit"}, "trigger": None,
             "source": "分析化学教材 误差与有效数字章"},
            {"rung_id": "L6-budget", "level": 6, "title": "测量不确定度",
             "concept": "把称量、读数、定容、移液的贡献合成扩展不确定度，判断偏差是否超出仪器所能解释的范围",
             "anchor": {"type": "comparison", "target": "error_budget"}, "trigger": None,
             "source": "JJF 1059.1-2012（GUM 国内版）"},
            {"rung_id": "L6-endpoint-error", "level": 6, "title": "指示剂终点误差可以定量算",
             "concept": "林邦误差公式；本实验未煮沸时甲基橙在计量点前约 0.15 mL 开始变色，煮沸后移到计量点后约 0.02 mL",
             "anchor": {"type": "comparison", "target": "titration_curve"}, "trigger": None,
             "source": "分析化学教材 终点误差节"},
            {"rung_id": "L7-gb601", "level": 7, "title": "标准方法怎么保证可靠",
             "concept": "GB/T 601 对标定的平行份数、人员与重复性限的要求，比教学要求严格",
             "anchor": {"type": "qc", "rule_id": "standardization_rpad"},
             "trigger": {"qc_fail": "standardization_rpad"},
             "source": "GB/T 601-2016（具体份数与限值待核）"},
            {"rung_id": "L7-next-dual-indicator", "level": 7, "title": "下一步：双指示剂法",
             "concept": "区分 Na₂CO₃–NaOH 与 Na₂CO₃–NaHCO₃（思考题 3、实验 4），检验总碱度偏高是否因含 NaOH",
             "anchor": {"type": "comparison", "target": "vs_limit[0]"}, "trigger": None,
             "source": "实验教材 实验 4"},
            {"rung_id": "L8-potentiometric", "level": 8, "title": "不用指示剂判终点",
             "concept": "电位滴定与 Gran 作图",
             "anchor": {"type": "comparison", "target": "titration_curve"}, "trigger": None,
             "source": "分析化学教材 电位滴定章"},
            {"rung_id": "L9-ocean-alkalinity", "level": 9, "title": "科研里的同一件事",
             "concept": "海水总碱度用开放式电位滴定测定，是碳循环研究的基础量",
             "anchor": {"type": "comparison", "target": "vs_limit[0]"}, "trigger": None,
             "source": "Dickson et al., Guide to Best Practices for Ocean CO₂ Measurements（PICES 3, 2007）, SOP 3b"},
        ],
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
