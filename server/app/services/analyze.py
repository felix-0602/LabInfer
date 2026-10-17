"""M4 分析编排：角色绑定 → 模型拟合 → 逆推 → 质控 → 三层参照判定。纯计算，存储由路由层注入。"""

from ..config import CONTRACT_VERSION
from ..models import REGISTRY, uncertainty as u
from ..models import qc as qc_engine


def _role_map(ctx: dict) -> dict:
    return {c["role"]: c for c in ctx["variables"]["columns"]}


def _pick(row: dict, col: dict | None, default=None):
    if col is None:
        return default
    v = row.get("values", {}).get(col["key"], default)
    if v is None:
        v = col.get("default", default)
    return v


def analyze(ctx: dict, mine_ds: dict, ref_datasets: dict[str, dict]) -> dict:
    model = REGISTRY[ctx["model"]]
    roles = _role_map(ctx)
    x_col, y_col = roles.get(model.x_role), roles.get(model.y_role)
    if not x_col or not y_col:
        raise ValueError(f"上下文缺少必需角色列: {model.x_role}/{model.y_role}")

    final_volume = ctx.get("model_params", {}).get("final_volume_ml", 50.0)

    rows = mine_ds.get("rows", [])
    std_rows = [r for r in rows if r.get("series") == "std"]
    sample_rows = [r for r in rows if str(r.get("series", "")).startswith("sample:")]
    crm_rows = [r for r in rows if r.get("series") == "qc:crm"]

    xs = [float(_pick(r, x_col)) for r in std_rows]
    ys = [float(_pick(r, y_col)) for r in std_rows]
    fit = model.fit(xs, ys)

    xs_t, ys_t = model.transform(xs, ys)
    transformed = [{
        "dataset_id": mine_ds["id"],
        "x_label": x_col["key"], "x_unit": x_col.get("unit", ""),
        "y_label": y_col["key"], "y_unit": y_col.get("unit", ""),
        "points": [
            {"point_id": r["id"], "x": round(x, 6), "y": round(y, 6)}
            for r, x, y in zip(std_rows, xs_t, ys_t)
        ],
    }]

    residuals = []
    g = u.grubbs_test(fit["residuals"])
    std_ids = [r["id"] for r in std_rows]
    for r, res in zip(std_rows, fit["residuals"]):
        residuals.append({
            "dataset_id": mine_ds["id"], "point_id": r["id"],
            "residual": round(float(res), 6),
            "outlier": False, "method": "grubbs", "p": None,
        })
    if g["outlier"] and g["index"] is not None and g["index"] < len(residuals):
        residuals[g["index"]]["outlier"] = True
        residuals[g["index"]]["p"] = round(g["p"], 4)

    def factors_of(row: dict) -> dict:
        v = _pick(row, roles.get("sample_volume"), default=50.0)
        d = _pick(row, roles.get("dilution_factor"), default=1)
        return {"sample_volume_ml": float(v), "final_volume_ml": float(final_volume),
                "dilution_factor": float(d)}

    predictions = []
    parallel_groups: dict[str, dict] = {}
    for r in sample_rows:
        y0 = float(_pick(r, y_col))
        c_hat, u95 = u.inverse_predict(fit, y0)
        f = factors_of(r)
        factor = (f["final_volume_ml"] / f["sample_volume_ml"]) * f["dilution_factor"]
        predictions.append({
            "dataset_id": mine_ds["id"], "point_id": r["id"],
            "value": round(c_hat, 6), "u95": round(u95 * factor, 6),
            "unit": x_col.get("unit", ""),
            "input": {y_col["key"]: y0},
            "factors": f,
            "as_reported": round(c_hat * factor, 6),
        })
        grp = parallel_groups.setdefault(r["series"], {"pids": [], "values": []})
        grp["pids"].append(r["id"])
        grp["values"].append(c_hat)

    crm_piece = None
    for r in crm_rows:
        y0 = float(_pick(r, y_col))
        c_hat, _ = u.inverse_predict(fit, y0)
        f = factors_of(r)
        factor = (f["final_volume_ml"] / f["sample_volume_ml"]) * f["dilution_factor"]
        crm_piece = {"point_id": r["id"], "value": c_hat * factor}

    pieces = {
        "dataset_id": mine_ds["id"],
        "fit": fit,
        "grubbs": g,
        "std_point_ids": std_ids,
        "parallel_groups": parallel_groups,
        "crm": crm_piece,
        "crm_reference": ctx.get("reference", {}).get("crm"),
    }
    qc_results = qc_engine.run_qc(ctx, pieces)

    comparison = {"vs_reference": [], "vs_limit": [], "vs_crm": None}
    for ref in ctx.get("reference", {}).get("datasets", []):
        ds = ref_datasets.get(ref["dataset_id"])
        if ds is None:
            continue
        rx = [row.get("values", {}).get(ref["columns"][model.x_role]) for row in ds.get("rows", [])]
        ry = [row.get("values", {}).get(ref["columns"][model.y_role]) for row in ds.get("rows", [])]
        pts = [(a, b) for a, b in zip(rx, ry) if a is not None and b is not None]
        if len(pts) < 3:
            continue
        rxs, rys = [p[0] for p in pts], [p[1] for p in pts]
        if ref.get("space") == "transformed":
            ref_fit = u.ols_fit(rxs, rys)
            ref_fit_t = None
        else:
            ref_fit = model.fit(rxs, rys)
            tx, ty = model.transform(rxs, rys)
            ref_fit_t = list(zip(tx, ty))
        comparison["vs_reference"].append({
            "dataset_id": ds["id"],
            "mine_slope": round(fit["slope"], 6),
            "ref_slope": round(ref_fit["slope"], 6),
            "deviation_pct": round((fit["slope"] - ref_fit["slope"]) / ref_fit["slope"] * 100, 2),
        })
        plot_pts = ref_fit_t or list(zip(rxs, rys))
        transformed.append({
            "dataset_id": ds["id"],
            "x_label": ref["columns"][model.x_role], "x_unit": "",
            "y_label": ref["columns"][model.y_role], "y_unit": "",
            "points": [{"point_id": f"L{i}", "x": round(a, 6), "y": round(b, 6)}
                       for i, (a, b) in enumerate(plot_pts)],
        })

    limits = ctx.get("reference", {}).get("limits", [])
    for pred in predictions:
        for lim in limits:
            value = pred["as_reported"]
            verdict = "exceed" if value > lim["value"] else "comply"
            comparison["vs_limit"].append({
                "point_id": pred["point_id"], "value": value, "limit": lim["value"],
                "label": lim.get("label", ""), "verdict": verdict,
            })

    if crm_piece and pieces["crm_reference"]:
        ref = pieces["crm_reference"]
        comparison["vs_crm"] = {
            "point_id": crm_piece["point_id"],
            "measured": round(crm_piece["value"], 6),
            "certified": ref["value"], "u95": ref["u95"],
            "within": abs(crm_piece["value"] - ref["value"]) <= ref["u95"],
        }

    fit_out = {
        "dataset_id": mine_ds["id"],
        "slope": round(fit["slope"], 6),
        "intercept": round(fit["intercept"], 6),
        "r2": round(fit["r2"], 6),
        "n": fit["n"],
        "derived": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in fit["derived"].items()},
    }
    for ci_key in ("slope_ci95",):
        if ci_key in fit_out["derived"]:
            fit_out["derived"][ci_key] = [round(x, 6) for x in fit["derived"][ci_key]]
    if "Ea_ci95" in fit["derived"]:
        fit_out["derived"]["Ea_ci95"] = [round(x, 6) for x in fit["derived"]["Ea_ci95"]]

    return {
        "schema_version": CONTRACT_VERSION,
        "context_id": ctx["id"],
        "model": model.id,
        "transformed": transformed,
        "fits": [fit_out],
        "predictions": predictions,
        "residuals": residuals,
        "qc_results": qc_results,
        "comparison": comparison,
    }
