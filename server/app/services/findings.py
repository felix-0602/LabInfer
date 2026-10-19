"""M5 模板结论：从 AnalysisResult 确定性生成 Finding[]。
LLM 路径（glm-5.3 + 数字溯源校验器）接入时替换生成器，本函数保留为降级路径与演示保底。"""

from ..config import CONTRACT_VERSION


def _num(v) -> str:
    return f"{v:.4g}"


def _f(fid, ftype, text, evidence, simulatable=False, simulation=None):
    return {
        "schema_version": CONTRACT_VERSION,
        "id": fid,
        "type": ftype,
        "text": text,
        "evidence": evidence,
        "simulatable": simulatable,
        "simulation": simulation,
    }


def _titration_findings(analysis: dict, ctx: dict, dataset: dict) -> list[dict]:
    findings = []
    fit = analysis["fits"][0]
    d = fit["derived"]
    ds_id = dataset["id"]

    findings.append(_f(
        "f_pattern", "pattern",
        f"标定——即用基准物质（组成稳定、能当标准砝码用的碳酸钠）把盐酸准确浓度"
        f"测出来的操作——三份平行线性良好："
        f"称的基准 Na₂CO₃ 越多、消耗的盐酸体积越大，滴定体积与称样量成过原点直线"
        f"（R²={_num(fit['r2'])}，n={fit['n']}），三份平均 c̄(HCl)={_num(d['c_hcl'])} mol/L"
        f"（过原点回归 {_num(d['c_regression'])}）。",
        [{"type": "fit", "dataset_id": ds_id}],
    ))

    curve = analysis.get("titration_curve")
    if curve:
        w = curve["indicator"]["dv_window_ml"]
        worst_ep = max(curve["endpoints"], key=lambda e: abs(e["dv_ml"])) \
            if curve["endpoints"] else None
        text = (f"理论滴定曲线（按溶解的 CO₂ 一点不逸出的封闭体系计算）上，化学计量点——"
                f"即盐酸恰好把碱全部中和的瞬间——pH {curve['ph_eq']}；"
                f"{curve['indicator']['name']} 变色窗 ΔV {w[0]}～{w[1]} mL"
                f"（曲线上 pH 落在指示剂变色区内的体积偏差区间）。")
        if worst_ep:
            text += (f"三份终点中 {worst_ep['point_id']} 偏离计量点最远"
                     f"（ΔV {worst_ep['dv_ml']} mL，pH {worst_ep['ph']}），"
                     f"提示这一份的终点判断偏差最大。")
        findings.append(_f("f_curve", "pattern", text,
                           [{"type": "comparison", "target": "titration_curve"}]))
        findings.append(_f(
            "f_co2", "suggestion",
            f"近终点前煮沸驱除 CO₂：溶解的 CO₂ 会形成缓冲——即有成分在抵抗 pH 变化——"
            f"带来两个后果：一是颜色变得慢、突跃（计量点附近 pH 陡变的一段）不再陡峭，"
            f"近终点更要半滴半滴地加；二是 pH 提前降进变色区，按「刚变橙就停」判，"
            f"终点会落在计量点之前"
            f"（理论曲线按 CO₂ 未逸出的封闭体系计算，计量点 pH {curve['ph_eq']}）。"
            f"驱除越彻底，突跃越陡、计量点 pH 越高，终点越靠近理论计量点。",
            [{"type": "comparison", "target": "titration_curve"}],
            simulatable=True,
            simulation={"param": "co2_retained_fraction", "from": 0, "to": 1, "unit": ""},
        ))

    budget = analysis.get("error_budget")
    if budget:
        findings.append(_f(
            "f_budget", "anomaly",
            f"三份标定的相对平均偏差——各次浓度偏离平均值的平均幅度占平均值的百分比——"
            f"实测 {round(budget['observed_rel_dev'] * 100, 2)}%，是仪器误差预算 "
            f"{budget['expected_rel_dev']}（把天平与滴定管的误差按方和根合成、取各份最大）的 "
            f"{budget['ratio']} 倍：散得这么开已经不能用称量与读数误差解释，"
            f"更可能是操作因素，比如各份终点颜色判断不一致。",
            [{"type": "comparison", "target": "error_budget"}],
        ))

    preds = analysis.get("predictions", [])
    mean_w = d.get("w_na2o_mean_pct")
    worst = None
    if mean_w is not None and preds:
        worst = max(preds, key=lambda p_: abs(p_["value"] - mean_w))
    for i, pred in enumerate(preds, start=1):
        lim = next((c for c in analysis["comparison"]["vs_limit"]
                    if c["point_id"] == pred["point_id"]), None)
        if not lim:
            continue
        judge = "高于" if lim["verdict"] == "exceed" else "不超过"
        gloss = ("总碱度——碱灰里所有能把酸中和掉的碱性成分合起来、折算成 Na₂O 的质量分数——"
                 if i == 1 else "总碱度（以 Na₂O 计）")
        findings.append(_f(
            f"f_conc{i}", "conclusion",
            f"碱灰平行 {i}（{pred['point_id']}）：{gloss}"
            f"({_num(pred['as_reported'])} ± {_num(pred['u95'])})%，"
            f"{judge}纯 Na₂CO₃ 理论值 {_num(lim['limit'])}%。",
            [{"type": "point", "dataset_id": ds_id, "point_id": pred["point_id"]},
             {"type": "comparison",
              "target": f"vs_limit[{analysis['comparison']['vs_limit'].index(lim)}]"}],
        ))

    if mean_w is not None and len(preds) >= 2:
        findings.append(_f(
            "f_mean", "conclusion",
            f"三份平行平均总碱度 {_num(mean_w)}%（相对平均偏差 "
            f"{_num(d['rel_avg_dev_w'] * 100)}%），报告值以平均值计。",
            [{"type": "fit", "dataset_id": ds_id}],
        ))

        if worst is not None:
            v0 = next(iter(worst["input"].values()))
            findings.append(_f(
                "f_worst", "anomaly",
                f"平行 {worst['point_id']} 三份里偏离平均值最多（总碱度 {_num(worst['as_reported'])}%，"
                f"滴定体积 {_num(v0)} mL），把相对平均偏差拉大到 "
                f"{_num(d['rel_avg_dev_w'] * 100)}%。先怀疑这一份终点滴过了头或读数看错："
                f"建议按 GB/T 601-2016 煮沸驱除 CO₂、冷却后再滴至终点，重做这一份。",
                [{"type": "point", "dataset_id": ds_id, "point_id": worst["point_id"]},
                 {"type": "qc", "rule_id": "parallel_rpd"}],
                simulatable=True,
                simulation={"param": "titrant_volume_delta", "from": -2, "to": 0, "unit": "mL"},
            ))

    for i, res in enumerate(analysis.get("residuals", []), start=1):
        if res["outlier"]:
            findings.append(_f(
                f"f_out{i}", "anomaly",
                f"标定第 {res['point_id']} 份的浓度偏离平均值 {res['residual']}，"
                f"格拉布斯检验——判断「这个可疑值是不是该剔除」的统计检验（GB/T 4883）——"
                f"判为离群，建议核对这一份的称量与滴定读数。",
                [{"type": "point", "dataset_id": ds_id, "point_id": res["point_id"]},
                 {"type": "qc", "rule_id": "outlier_grubbs"}],
            ))

    for i, qc in enumerate(analysis.get("qc_results", []), start=1):
        if not qc["pass"]:
            value = qc.get("value_pct", qc.get("value"))
            limit_pct = qc.get("limit")
            if isinstance(limit_pct, (int, float)) and limit_pct <= 1:
                limit_pct = f"{limit_pct * 100:g}%"
            findings.append(_f(
                f"f_qc{i}", "anomaly",
                f"质控规则 {qc['rule_id']} 未通过（实测 {value}%，限值 "
                f"{limit_pct}），依据 {qc.get('citation', '')}。",
                [{"type": "qc", "rule_id": qc["rule_id"]}],
            ))

    return findings


def compose_findings(analysis: dict, ctx: dict, dataset: dict) -> list[dict]:
    if analysis.get("model") == "titration_standardization":
        return _titration_findings(analysis, ctx, dataset)
    findings = []
    fit = analysis["fits"][0]
    ds_id = dataset["id"]

    findings.append(_f(
        "f_pattern", "pattern",
        f"标准曲线线性良好：R²={_num(fit['r2'])}（n={fit['n']}），斜率 {_num(fit['slope'])}，"
        f"截距 {_num(fit['intercept'])}。",
        [{"type": "fit", "dataset_id": ds_id}],
    ))

    row_by_id = {r["id"]: r for r in dataset.get("rows", [])}
    for i, pred in enumerate(analysis.get("predictions", []), start=1):
        lim = next((c for c in analysis["comparison"]["vs_limit"]
                    if c["point_id"] == pred["point_id"]), None)
        name = row_by_id.get(pred["point_id"], {}).get("series", pred["point_id"])
        if lim:
            judge = "超过" if lim["verdict"] == "exceed" else "达到"
            findings.append(_f(
                f"f_conc{i}", "conclusion",
                f"{name}：浓度 {_num(pred['as_reported'])}±{_num(pred['u95'])} {pred['unit']}，"
                f"{judge}{lim['label']}（限值 {_num(lim['limit'])} {lim.get('unit', '')}）。",
                [{"type": "point", "dataset_id": ds_id, "point_id": pred["point_id"]},
                 {"type": "comparison", "target": f"vs_limit[{analysis['comparison']['vs_limit'].index(lim)}]"}],
                simulatable=True,
                simulation={"param": "dilution_factor", "from": 1, "to": 10, "unit": ""},
            ))

    for i, res in enumerate(analysis.get("residuals", []), start=1):
        if res["outlier"]:
            findings.append(_f(
                f"f_out{i}", "anomaly",
                f"标准曲线点 {res['point_id']} 残差 {res['residual']}，"
                f"格拉布斯检验判为离群（GB/T 4883），建议核对该管配制与读数。",
                [{"type": "point", "dataset_id": ds_id, "point_id": res["point_id"]},
                 {"type": "qc", "rule_id": "outlier_grubbs"}],
            ))

    for i, qc in enumerate(analysis.get("qc_results", []), start=1):
        if not qc["pass"]:
            findings.append(_f(
                f"f_qc{i}", "anomaly",
                f"质控规则 {qc['rule_id']} 未通过（实测 {qc.get('value')}，限值 "
                f"{qc.get('limit')}），依据 {qc.get('citation', '')}。",
                [{"type": "qc", "rule_id": qc["rule_id"]}],
            ))

    for i, vr in enumerate(analysis["comparison"].get("vs_reference", []), start=1):
        findings.append(_f(
            f"f_ref{i}", "pattern",
            f"本实验标曲斜率 {vr['mine_slope']}，文献（{vr['dataset_id']}）为 {vr['ref_slope']}，"
            f"偏离 {vr['deviation_pct']}%。灵敏度差异通常来自光程、仪器与试剂批次，"
            f"对比时须核对口径。",
            [{"type": "comparison", "target": f"vs_reference[{i - 1}]"}],
        ))

    crm = analysis["comparison"].get("vs_crm")
    if crm:
        verdict = "落在" if crm["within"] else "超出"
        findings.append(_f(
            "f_crm", "conclusion",
            f"质控样（CRM）测定值 {crm['measured']} mg/L，{verdict}证书真值 "
            f"{crm['certified']}±{crm['u95']} mg/L 的不确定度区间，方法准确度"
            f"{'可信' if crm['within'] else '存疑'}。",
            [{"type": "comparison", "target": "vs_crm"},
             {"type": "qc", "rule_id": "crm_within_u95"}],
        ))

    return findings


def attach_ladder(findings: list[dict], ctx: dict, analysis: dict) -> list[dict]:
    """按 wiki.md#讲解阶梯 的规则给结论挂讲解（契约 0.7.0 可选字段）。

    - 锚点必须逐字出现在本条 evidence 里（同 type；comparison 比 target、qc 比 rule_id）；
    - trigger.qc_fail 要求该质控规则本次未通过；
    - 出处标「待核」的级不进演示；
    - 只挂 base_level 之上的级，往上递最多 2 级（level 最低的优先，不越级）。
    """
    ladder = ctx.get("ladder") or {}
    rungs = ladder.get("rungs") or []
    base = ladder.get("base_level") or 0
    failed = {q["rule_id"] for q in analysis.get("qc_results", []) if not q.get("pass")}
    avail = [r for r in rungs
             if r.get("level", 0) > base and "待核" not in (r.get("source") or "")]

    def anchored(rung: dict, evidence: list[dict]) -> bool:
        a = rung.get("anchor") or {}
        for ev in evidence:
            if ev.get("type") != a.get("type"):
                continue
            if a.get("type") == "comparison" and ev.get("target") != a.get("target"):
                continue
            if a.get("type") == "qc" and ev.get("rule_id") != a.get("rule_id"):
                continue
            return True
        return False

    for f in findings:
        trig_ok = lambda r: (not r.get("trigger")
                             or r["trigger"].get("qc_fail") in failed)
        hits = sorted((r for r in avail if anchored(r, f.get("evidence") or []) and trig_ok(r)),
                      key=lambda r: r["level"])
        if hits:
            f["ladder"] = [{"rung_id": r["rung_id"], "level": r["level"],
                            "text": f"{r['title']}：{r['concept']}"} for r in hits[:2]]
    return findings
