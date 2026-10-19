"""M5 结论校验器：数字溯源 + evidence 存在性。LLM 输出必须过这一关，模板输出为信任路径。"""

import re

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")
_ALLOWED_TYPES = {"pattern", "conclusion", "anomaly", "suggestion"}
_ALLOWED_EVIDENCE = {"point", "fit", "qc", "comparison"}


def collect_numbers(*sources) -> list[float]:
    out: list[float] = []
    def walk(v):
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, (int, float)):
            out.append(float(v))
        elif isinstance(v, str):
            # 标准号/限值标签（如 GB 3838-2002、HJ 630-2011）中的数字也进白名单
            out.extend(float(x) for x in _NUM_RE.findall(v))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    for s in sources:
        walk(s)
    return out


def _number_allowed(n: float, whitelist: list[float], rtol: float = 0.005) -> bool:
    for w in whitelist:
        if abs(n - w) <= max(abs(w) * rtol, 1e-9):
            return True
    return False


def validate_findings(findings: list[dict], analysis: dict, dataset: dict, ctx: dict):
    """返回 (保留, 丢弃原因列表)。"""
    whitelist = collect_numbers(
        analysis.get("fits"), analysis.get("predictions"), analysis.get("residuals"),
        analysis.get("qc_results"), analysis.get("comparison"),
        analysis.get("titration_curve"), analysis.get("error_budget"),
        ctx.get("reference"), ctx.get("qc_rules"))
    point_ids = {r["id"] for r in dataset.get("rows", [])}
    ds_ids = {dataset.get("id")}
    qc_ids = {q.get("rule_id") for q in analysis.get("qc_results", [])}
    n_limit = len(analysis.get("comparison", {}).get("vs_limit", []))
    n_ref = len(analysis.get("comparison", {}).get("vs_reference", []))
    has_crm = analysis.get("comparison", {}).get("vs_crm") is not None
    has_curve = analysis.get("titration_curve") is not None      # 0.7.0 可选节
    has_budget = analysis.get("error_budget") is not None

    kept, dropped = [], []
    for raw in findings:
        why = None
        if not isinstance(raw, dict):
            why = "非对象"
        elif raw.get("type") not in _ALLOWED_TYPES:
            why = f"非法 type: {raw.get('type')}"
        elif not raw.get("text") or not str(raw.get("text")).strip():
            why = "text 为空"
        else:
            for n in (float(x) for x in _NUM_RE.findall(str(raw["text"]))):
                if not _number_allowed(n, whitelist):
                    why = f"数字无溯源: {n:g}"
                    break
        if why is None:
            evs = raw.get("evidence") or []
            if not isinstance(evs, list) or not evs:
                why = "evidence 为空"
            else:
                for ev in evs:
                    t = ev.get("type")
                    if t == "point":
                        if ev.get("dataset_id") not in ds_ids or ev.get("point_id") not in point_ids:
                            why = f"point 不存在: {ev.get('point_id')}"
                            break
                    elif t == "fit":
                        if ev.get("dataset_id") not in ds_ids:
                            why = "fit 数据集不存在"
                            break
                    elif t == "qc":
                        if ev.get("rule_id") not in qc_ids:
                            why = f"qc 规则不存在: {ev.get('rule_id')}"
                            break
                    elif t == "comparison":
                        tgt = str(ev.get("target", ""))
                        ok = (
                            (tgt.startswith("vs_limit[") and _idx(tgt) < n_limit)
                            or (tgt.startswith("vs_reference[") and _idx(tgt) < n_ref)
                            or (tgt == "vs_crm" and has_crm)
                            or (tgt == "titration_curve" and has_curve)
                            or (tgt == "error_budget" and has_budget)
                        )
                        if not ok:
                            why = f"comparison 目标不存在: {tgt}"
                            break
                    else:
                        why = f"非法 evidence type: {t}"
                        break
        if why is None:
            kept.append(raw)
        else:
            dropped.append(why)
    return kept, dropped


def _idx(target: str) -> int:
    try:
        return int(target[target.index("[") + 1:target.index("]")])
    except (ValueError, IndexError):
        return 10 ** 9
