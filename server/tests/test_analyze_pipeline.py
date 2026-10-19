import pytest

from app.services.analyze import analyze
from scripts.seed_demo import build_demo_objects


@pytest.fixture()
def demo_result():
    mine, ctx = build_demo_objects()
    return analyze(ctx, mine, {}), ctx, mine


def test_fit_matches_recorded_values(demo_result):
    """对账手写记录页：c̄=0.1027、回归 0.1029、R²>0.999。"""
    result, _, _ = demo_result
    fit = result["fits"][0]
    d = fit["derived"]
    assert fit["slope"] == pytest.approx(183.45, abs=0.2)   # V = k·m，mL/g
    assert fit["intercept"] == 0.0
    assert fit["r2"] > 0.999
    assert fit["n"] == 3
    assert d["c_hcl"] == pytest.approx(0.1027, abs=0.0002)
    assert d["c_regression"] == pytest.approx(0.1029, abs=0.0002)


def test_prediction_w_matches_recorded_values(demo_result):
    """对账记录页：三份 59.10 / 62.58 / 60.22，均值 60.63。"""
    result, _, _ = demo_result
    by_id = {p["point_id"]: p for p in result["predictions"]}
    assert by_id["s1"]["as_reported"] == pytest.approx(59.10, abs=0.02)
    assert by_id["s2"]["as_reported"] == pytest.approx(62.58, abs=0.02)
    assert by_id["s3"]["as_reported"] == pytest.approx(60.22, abs=0.02)
    d = result["fits"][0]["derived"]
    assert d["w_na2o_mean_pct"] == pytest.approx(60.63, abs=0.02)


def test_qc_runs_all_declared_rules(demo_result):
    result, ctx, _ = demo_result
    ran = {q["rule_id"] for q in result["qc_results"]}
    declared = {r["rule_id"] for r in ctx["qc_rules"]}
    assert declared <= ran
    std_rpad = next(q for q in result["qc_results"] if q["rule_id"] == "standardization_rpad")
    assert not std_rpad["pass"]                       # 1.31% > 0.2%
    assert std_rpad["value"] == pytest.approx(0.0131, abs=0.0005)
    par_rpd = next(q for q in result["qc_results"] if q["rule_id"] == "parallel_rpd")
    assert not par_rpd["pass"]                        # 2.14% > 0.2%
    assert par_rpd["value"] == pytest.approx(0.0214, abs=0.0005)
    grubbs = next(q for q in result["qc_results"] if q["rule_id"] == "outlier_grubbs")
    assert grubbs["pass"]                             # n=3 检验功效低，未判离群
    assert grubbs["value"] == pytest.approx(1.074, abs=0.01)


def test_comparison_against_theoretical_limit(demo_result):
    result, _, _ = demo_result
    verdicts = {c["point_id"]: c["verdict"] for c in result["comparison"]["vs_limit"]}
    assert set(verdicts) == {"s1", "s2", "s3"}
    assert all(v == "exceed" for v in verdicts.values())   # 均高于纯品理论值 58.47%
    assert result["comparison"]["vs_reference"] == []
    assert result["comparison"]["vs_crm"] is None


def test_findings_reference_real_objects(demo_result):
    from app.services.findings import compose_findings
    result, ctx, mine = demo_result
    findings = compose_findings(result, ctx, mine)
    assert findings, "至少一条模板结论"
    point_ids = {r["id"] for r in mine["rows"]}
    qc_ids = {q["rule_id"] for q in result["qc_results"]}
    for f in findings:
        assert f["evidence"]
        for ev in f["evidence"]:
            if ev["type"] == "point":
                assert ev["point_id"] in point_ids
            elif ev["type"] == "qc":
                assert ev["rule_id"] in qc_ids
    sim_params = {f["id"]: f["simulation"]["param"] for f in findings if f["simulatable"]}
    assert sim_params.get("f_worst") == "titrant_volume_delta"
    assert sim_params.get("f_co2") == "co2_retained_fraction"   # 0.7.0：煮沸推演入口
