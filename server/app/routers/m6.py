from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from ..config import CONTRACT_VERSION

router = APIRouter(prefix="/api/m6", tags=["m6"])


class SimulateRequest(BaseModel):
    # 契约字段名是 from（Python 关键字），frm 兼容旧调用
    model_config = ConfigDict(populate_by_name=True)

    schema_version: str = CONTRACT_VERSION
    context_id: str
    finding_id: str
    param: str
    frm: float = Field(alias="from")
    to: float
    unit: str = ""


def _simulate_dilution(pred: dict, frm: float, to: float, mid: float) -> dict:
    y0 = next(iter(pred["input"].values()))
    c0 = pred["value"]
    n = 20
    step = (to - frm) / (n - 1) if n > 1 else 1
    curve = []
    for i in range(n):
        factor = frm + step * i
        if factor <= 0:
            continue
        curve.append({"x": round(c0 / factor, 6), "y": round(y0 / factor, 6)})
    return {
        "schema_version": CONTRACT_VERSION,
        "finding_id": "",
        "predicted": {"dilution_factor": mid, "A": round(y0 / mid, 6)},
        "curve": curve,
    }


def _simulate_temperature(fit: dict, frm: float, to: float, mid: float) -> dict:
    def line(T):
        x = 1.0 / (T + 273.15)
        return fit["slope"] * x + fit["intercept"]

    n = 20
    step = (to - frm) / (n - 1) if n > 1 else 1
    import math
    curve = [{"x": round(1.0 / (frm + step * i + 273.15), 6),
              "y": round(line(frm + step * i), 6)} for i in range(n)]
    return {
        "schema_version": CONTRACT_VERSION,
        "finding_id": "",
        "predicted": {"temperature": mid,
                      "t": round(1.0 / math.exp(line(mid)), 3)},
        "curve": curve,
    }


def _simulate_titration_delta(preds: list[dict], frm: float, to: float, mid: float) -> dict:
    """终点体积系统偏差 ΔV 对总碱度的推演：w ∝ V。取偏离平行均值最多的一份。"""
    values = [p_["as_reported"] for p_ in preds]
    mean = sum(values) / len(values)
    pred = max(preds, key=lambda p_: abs(p_["as_reported"] - mean))
    v0 = next(iter(pred["input"].values()))
    w0 = pred["as_reported"]

    n = 20
    step = (to - frm) / (n - 1) if n > 1 else 1
    curve = []
    for i in range(n):
        delta = frm + step * i
        if v0 + delta <= 0:
            continue
        curve.append({"x": round(delta, 4),
                      "y": round(w0 * (v0 + delta) / v0, 4)})
    return {
        "schema_version": CONTRACT_VERSION,
        "finding_id": "",
        "predicted": {"titrant_volume_delta_ml": mid,
                      "w_na2o_pct": round(w0 * (v0 + mid) / v0, 4)},
        "curve": curve,
    }


def _simulate_co2_retention(curve: dict, frm: float, to: float, mid: float) -> dict:
    """残留 CO₂ 比例对滴定曲线的影响（0.7.0）：x 为 ΔV（mL），y 为 pH。
    fraction=1 即封闭体系理论曲线；比例越小代表煮沸驱除越多，总碳按比例缩减，
    计量点 pH 上移、突跃更陡。近似只在计量点附近窗口内有意义。"""
    from ..models.titration import ph_at

    basis = curve["basis"]
    params = {"pka1": basis["pka1"], "pka2": basis["pka2"],
              "molar_mass_na2co3_g_mol": basis.get("molar_mass_na2co3", 105.99),
              "initial_water_ml": basis.get("initial_water_ml", 30.0)}
    v_eq, mass, c = basis["v_eq_ml"], basis["mass_g"], basis["c_mol_l"]

    n = 161
    step = 4.0 / (n - 1)
    pts = [{"x": round(-2.0 + step * i, 3),
            "y": round(ph_at(v_eq - 2.0 + step * i, mass, c, params,
                             co2_retained=mid), 3)}
           for i in range(n)]
    return {
        "schema_version": CONTRACT_VERSION,
        "finding_id": "",
        "predicted": {"co2_retained_fraction": mid,
                      "ph_eq": round(ph_at(v_eq, mass, c, params,
                                           co2_retained=mid), 2)},
        "curve": pts,
    }


@router.post("/simulate")
def simulate(body: SimulateRequest, request: Request):
    store = request.app.state.store
    analysis = store.get_analysis(body.context_id)
    if analysis is None:
        return JSONResponse(status_code=422, content={
            "error": {"code": "NO_ANALYSIS", "message": "先调用 POST /api/m4/analyze", "detail": {}}})

    mid = (body.frm + body.to) / 2
    if body.param == "dilution_factor":
        preds = analysis.get("predictions", [])
        if not preds:
            return JSONResponse(status_code=422, content={
                "error": {"code": "NOT_SIMULATABLE", "message": "无可推演的样品", "detail": {}}})
        out = _simulate_dilution(preds[0], body.frm, body.to, mid)
    elif body.param == "temperature":
        fit = analysis["fits"][0]
        out = _simulate_temperature(fit, body.frm, body.to, mid)
    elif body.param == "titrant_volume_delta":
        preds = analysis.get("predictions", [])
        if len(preds) < 2:
            return JSONResponse(status_code=422, content={
                "error": {"code": "NOT_SIMULATABLE", "message": "无可推演的平行样品", "detail": {}}})
        out = _simulate_titration_delta(preds, body.frm, body.to, mid)
    elif body.param == "co2_retained_fraction":
        curve = analysis.get("titration_curve")
        if not curve:
            return JSONResponse(status_code=422, content={
                "error": {"code": "NOT_SIMULATABLE",
                          "message": "分析结果缺少 titration_curve（model_params 需要 pka1/pka2）",
                          "detail": {}}})
        frm = max(0.0, min(body.frm, body.to))    # 比例只在 0～1 有意义
        to = min(1.0, max(body.frm, body.to))
        out = _simulate_co2_retention(curve, frm, to, (frm + to) / 2)
    else:
        return JSONResponse(status_code=422, content={
            "error": {"code": "NOT_SIMULATABLE",
                      "message": f"参数不可推演: {body.param}", "detail": {}}})
    out["finding_id"] = body.finding_id
    return out
