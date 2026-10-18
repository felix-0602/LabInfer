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
        f"基准 Na₂CO₃ 标定线性良好：滴定体积与称样量成过原点直线（R²={_num(fit['r2'])}，"
        f"n={fit['n']}），三份平行平均 c̄(HCl)={_num(d['c_hcl'])} mol/L"
        f"（过原点回归 {_num(d['c_regression'])}）。",
        [{"type": "fit", "dataset_id": ds_id}],
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
        findings.append(_f(
            f"f_conc{i}", "conclusion",
            f"碱灰平行 {i}（{pred['point_id']}）：总碱度（以 Na₂O 计）"
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
                f"平行 {worst['point_id']} 偏离均值最多（{_num(worst['as_reported'])}%，"
                f"滴定体积 {_num(v0)} mL），把相对平均偏差拉大到 "
                f"{_num(d['rel_avg_dev_w'] * 100)}%。怀疑终点过头或读数错误，"
                f"建议按 GB/T 601-2016 煮沸驱除 CO₂ 后冷却再滴至终点，重做该份。",
                [{"type": "point", "dataset_id": ds_id, "point_id": worst["point_id"]},
                 {"type": "qc", "rule_id": "parallel_rpd"}],
                simulatable=True,
                simulation={"param": "titrant_volume_delta", "from": -2, "to": 0, "unit": "mL"},
            ))

    for i, res in enumerate(analysis.get("residuals", []), start=1):
        if res["outlier"]:
            findings.append(_f(
                f"f_out{i}", "anomaly",
                f"标定第 {res['point_id']} 份浓度偏离平均 {res['residual']}，"
                f"格拉布斯检验判为离群（GB/T 4883），建议核对称量与滴定读数。",
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
                f"{name}：氨氮浓度 {_num(pred['as_reported'])}±{_num(pred['u95'])} mg/L，"
                f"{judge}{lim['label']}（限值 {_num(lim['limit'])} mg/L）。",
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
