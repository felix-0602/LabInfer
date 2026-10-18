from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..config import CONTRACT_VERSION

router = APIRouter(prefix="/api/m6", tags=["m6"])


class SimulateRequest(BaseModel):
    schema_version: str = CONTRACT_VERSION
    context_id: str
    finding_id: str
    param: str
    frm: float
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
    else:
        return JSONResponse(status_code=422, content={
            "error": {"code": "NOT_SIMULATABLE",
                      "message": f"参数不可推演: {body.param}", "detail": {}}})
    out["finding_id"] = body.finding_id
    return out
