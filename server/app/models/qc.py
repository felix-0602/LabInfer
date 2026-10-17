"""质控规则引擎：按 ExperimentContext.qc_rules 逐条执行，输出挂条文的判定。"""


def _rpd(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    return abs(values[0] - values[1]) / mean


def run_qc(ctx: dict, pieces: dict) -> list[dict]:
    results = []
    for rule in ctx.get("qc_rules", []):
        rid = rule["rule_id"]
        params = rule.get("params", {})
        citation = rule.get("citation", "")
        fn = _RULES.get(rid)
        if fn is None:
            continue
        r = fn(pieces, params)
        if r is None:
            continue
        r.update({"rule_id": rid, "citation": citation})
        results.append(r)
    return results


def _calibration_r2(pieces, params):
    fit = pieces.get("fit")
    if not fit:
        return None
    value = fit.get("r2")
    return {
        "pass": bool(value >= params.get("min", 0.999)),
        "value": value,
        "limit": params.get("min", 0.999),
        "subjects": [],
    }


def _parallel_rpd(pieces, params):
    groups = pieces.get("parallel_groups", {})
    worst = None
    for name, grp in groups.items():
        if len(grp["values"]) < 2:
            continue
        rpd = _rpd(grp["values"])
        if worst is None or rpd > worst["value"]:
            worst = {
                "value": rpd,
                "subjects": [
                    {"dataset_id": pieces["dataset_id"], "point_id": pid} for pid in grp["pids"]
                ],
            }
    if worst is None:
        return None
    return {
        "pass": bool(worst["value"] <= params.get("max", 0.10)),
        "value": worst["value"],
        "limit": params.get("max", 0.10),
        "subjects": worst["subjects"],
    }


def _outlier_grubbs(pieces, params):
    g = pieces.get("grubbs")
    if not g or g.get("index") is None:
        return None
    std_ids = pieces.get("std_point_ids", [])
    idx = g["index"]
    subj = [{"dataset_id": pieces["dataset_id"], "point_id": std_ids[idx]}] if idx < len(std_ids) else []
    return {
        "pass": not g["outlier"],
        "value": g["G"],
        "limit": g["G_crit"],
        "subjects": subj,
    }


def _crm_within_u95(pieces, params):
    crm = pieces.get("crm")
    ref = pieces.get("crm_reference")
    if not crm or not ref:
        return None
    measured, certified, u95 = crm["value"], ref["value"], ref["u95"]
    return {
        "pass": bool(abs(measured - certified) <= u95),
        "value": measured,
        "certified": certified,
        "u95": u95,
        "subjects": [{"dataset_id": pieces["dataset_id"], "point_id": crm["point_id"]}],
    }


_RULES = {
    "calibration_r2": _calibration_r2,
    "parallel_rpd": _parallel_rpd,
    "outlier_grubbs": _outlier_grubbs,
    "crm_within_u95": _crm_within_u95,
}
