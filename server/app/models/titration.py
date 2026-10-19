"""0.7.0 滴定曲线与误差预算：电荷平衡解 pH（封闭体系）、指示剂窗口、终点偏差、
仪器误差预算。纯函数。对账目标（契约 0.7.0 示例）：v_eq 30.67 mL、pH_eq 3.97、
变色窗 ΔV[-0.15, +0.46]、p2 ΔV -0.649 / pH 4.96、预算 0.0015 / 比率 8.7。"""

import math

KW = 1e-14
_PH_LO, _PH_HI = 0.5, 13.0
_BISECT = 80


def _alphas(h: float, ka1: float, ka2: float) -> float:
    """碳酸各型体贡献系数和：α1 + 2·α2（每摩尔碳的平均负电荷）。"""
    d = h * h + ka1 * h + ka1 * ka2
    return (ka1 * h + 2 * ka1 * ka2) / d


def ph_at(v_ml: float, mass_g: float, c_mol_l: float, params: dict,
          co2_retained: float = 1.0) -> float:
    """封闭体系电荷平衡解 pH：[H⁺]+[Na⁺] = [OH⁻]+[HCO₃⁻]+2[CO₃²⁻]+[Cl⁻]。

    co2_retained 为残留 CO₂ 比例（M6 推演用）：1=未煮沸的封闭体系（0.7.0 曲线口径），
    越小代表煮沸驱除越多，总碳按比例缩减。近似只对计量点附近的窗口有意义。
    """
    ka1, ka2 = 10.0 ** -params["pka1"], 10.0 ** -params["pka2"]
    molar_mass = params.get("molar_mass_na2co3_g_mol", 105.99)
    water_ml = params.get("initial_water_ml", 30.0)
    n_c = mass_g / molar_mass
    vt = (water_ml + v_ml) / 1000.0
    na, cl = 2 * n_c / vt, c_mol_l * v_ml / 1000.0 / vt
    ct = co2_retained * n_c / vt

    def f(ph: float) -> float:
        h = 10.0 ** -ph
        return h + na - KW / h - ct * _alphas(h, ka1, ka2) - cl

    lo, hi = _PH_LO, _PH_HI
    for _ in range(_BISECT):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _dv_of_ph(target_ph: float, v_eq: float, mass_g: float, c: float, params: dict) -> float:
    lo, hi = v_eq - 2.0, v_eq + 2.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if ph_at(mid, mass_g, c, params) > target_ph:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2 - v_eq


def titration_curve_section(std_rows: list[dict], c_mean: float, params: dict,
                            ds_id: str) -> dict | None:
    """契约 0.7.0 AnalysisResult.titration_curve。model_params 缺 pka1/pka2 时返回 None。"""
    if "pka1" not in params or "pka2" not in params or not std_rows:
        return None
    molar_mass = params.get("molar_mass_na2co3_g_mol", 105.99)
    rows = sorted(std_rows, key=lambda r: r["values"]["m"])
    mid = rows[len(rows) // 2]                       # 称样量居中的一份作图
    m_mid, v_mid_id = mid["values"]["m"], mid["id"]
    v_eq = 2 * m_mid / (molar_mass * c_mean) * 1000.0

    theory = []
    step = 0.025
    x = -2.0
    while x <= 2.0 + 1e-9:
        theory.append({"x": round(x, 3), "y": round(ph_at(v_eq + x, m_mid, c_mean, params), 3)})
        x += step

    indicator = params.get("indicator") or {}
    ph_lo, ph_hi = (indicator.get("ph_range") or [3.1, 4.4])
    window = [_dv_of_ph(ph_hi, v_eq, m_mid, c_mean, params),    # 变色起点（pH 高端）
              _dv_of_ph(ph_lo, v_eq, m_mid, c_mean, params)]    # 变色终点（pH 低端）

    endpoints = []
    for r in std_rows:
        m_i, v_i = r["values"]["m"], r["values"]["V"]
        dv = v_i - 2 * m_i / (molar_mass * c_mean) * 1000.0
        if -2.0 <= dv <= 2.0:
            endpoints.append({"dataset_id": ds_id, "point_id": r["id"],
                              "dv_ml": round(dv, 3),
                              "ph": round(ph_at(v_eq + dv, m_mid, c_mean, params), 2)})

    return {
        "x_label": "ΔV", "x_unit": "mL", "y_label": "pH", "y_unit": "",
        "basis": {"point_id": v_mid_id, "v_eq_ml": round(v_eq, 2), "closed_system": True,
                  "pka1": params["pka1"], "pka2": params["pka2"],
                  # M6 重建曲线所需的完整参数（契约示例字段的超集，开放对象）
                  "c_mol_l": round(c_mean, 6), "mass_g": m_mid,
                  "initial_water_ml": params.get("initial_water_ml", 30.0),
                  "molar_mass_na2co3": molar_mass},
        "theory": theory,
        "ph_eq": round(ph_at(v_eq, m_mid, c_mean, params), 2),
        "indicator": {"name": indicator.get("name", ""), "ph_range": [ph_lo, ph_hi],
                      "dv_window_ml": [round(window[0], 2), round(window[1], 2)]},
        "endpoints": endpoints,
        "literature": [],
    }


def convert_literature_curve(ref_ds: dict, ref_decl: dict, curve: dict) -> dict | None:
    """把文献滴定曲线换到与理论曲线同一 ΔV 坐标。

    ref_decl.columns 需含 titrant_volume / ph 两个角色；meta.v_eq_ml 给文献图的
    计量点体积（space=raw 时先把文献体积换算成滴定分数，transformed 则横轴已是分数）。
    """
    cols = ref_decl.get("columns") or {}
    vx, vy = cols.get("titrant_volume"), cols.get("ph")
    meta = ref_decl.get("meta") or {}
    if not vx or not vy:
        return None
    v_eq_lit = meta.get("v_eq_ml")
    space = ref_decl.get("space", "raw")
    v_eq_ours = curve["basis"]["v_eq_ml"]
    pts = []
    for r in ref_ds.get("rows", []):
        x = r.get("values", {}).get(vx)
        y = r.get("values", {}).get(vy)
        if x is None or y is None:
            continue
        if space == "transformed":
            a = float(x) if float(x) <= 2.0 else float(x) / 100.0   # 分数或百分数
        else:
            if not v_eq_lit:
                return None
            a = float(x) / float(v_eq_lit)
        pts.append({"x": round((a - 1.0) * v_eq_ours, 3), "y": round(float(y), 3)})
    if len(pts) < 2:
        return None
    return {"dataset_id": ref_ds["id"], "points": pts}


def error_budget_section(std_rows: list[dict], params: dict, ds_id: str,
                         observed_rel_dev: float) -> dict | None:
    """契约 0.7.0 AnalysisResult.error_budget。缺 balance/burette 误差常数时返回 None。"""
    bal = params.get("balance_error_g")
    bur = params.get("burette_error_ml")
    if not bal or not bur or not std_rows:
        return None
    items, worst = [], 0.0
    for r in std_rows:
        m_i, v_i = r["values"]["m"], r["values"]["V"]
        rel = math.hypot(2 * bal / m_i, 2 * bur / v_i)
        worst = max(worst, rel)
        items.append({"source": "天平两次称量", "rel": round(2 * bal / m_i, 4),
                      "subject": {"dataset_id": ds_id, "point_id": r["id"]}})
        items.append({"source": "滴定管两次读数", "rel": round(2 * bur / v_i, 4),
                      "subject": {"dataset_id": ds_id, "point_id": r["id"]}})
    ratio = observed_rel_dev / round(worst, 4) if worst else 0.0
    return {
        "items": items,
        "expected_rel_dev": round(worst, 4),
        "observed_rel_dev": round(observed_rel_dev, 6),
        "ratio": round(ratio, 1),
    }
