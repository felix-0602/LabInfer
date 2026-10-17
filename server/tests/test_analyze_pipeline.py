import pytest

from app.services.analyze import analyze
from scripts.seed_demo import build_demo_objects


@pytest.fixture()
def demo_result():
    mine, lit, ctx = build_demo_objects()
    return analyze(ctx, mine, {lit["id"]: lit}), ctx, mine


def test_fit_matches_recorded_values(demo_result):
    result, _, _ = demo_result
    fit = result["fits"][0]
    assert fit["slope"] == pytest.approx(0.4026, abs=0.002)
    assert fit["r2"] > 0.999
    assert fit["n"] == 7


def test_prediction_applies_volume_and_dilution_factors(demo_result):
    result, _, _ = demo_result
    by_id = {p["point_id"]: p for p in result["predictions"]}
    assert by_id["s1a"]["as_reported"] == pytest.approx(2.78, abs=0.02)
    assert by_id["s2"]["as_reported"] == pytest.approx(0.79, abs=0.02)
    assert by_id["s3"]["as_reported"] == pytest.approx(119.6, abs=1.0)


def test_qc_runs_all_declared_rules(demo_result):
    result, ctx, _ = demo_result
    ran = {q["rule_id"] for q in result["qc_results"]}
    declared = {r["rule_id"] for r in ctx["qc_rules"]}
    assert declared <= ran
    rpd = next(q for q in result["qc_results"] if q["rule_id"] == "parallel_rpd")
    assert rpd["pass"] and rpd["value"] == pytest.approx(0.0087, abs=0.002)
    crm = next(q for q in result["qc_results"] if q["rule_id"] == "crm_within_u95")
    assert crm["pass"]


def test_comparison_three_layers(demo_result):
    result, _, _ = demo_result
    vr = result["comparison"]["vs_reference"][0]
    assert vr["ref_slope"] == pytest.approx(0.13933, abs=1e-3)
    assert vr["deviation_pct"] == pytest.approx(189, abs=5)
    limits = {c["point_id"]: c for c in result["comparison"]["vs_limit"]}
    assert limits["s1a"]["verdict"] == "exceed"
    assert limits["s2"]["verdict"] == "comply"
    assert result["comparison"]["vs_crm"]["within"] is True


def test_findings_reference_real_objects(demo_result):
    from app.services.findings import compose_findings
    result, ctx, mine = demo_result
    findings = compose_findings(result, ctx, mine)
    assert findings, "至少一条模板结论"
    point_ids = {r["id"] for r in mine["rows"]}
    for f in findings:
        assert f["evidence"]
        for ev in f["evidence"]:
            if ev["type"] == "point":
                assert ev["point_id"] in point_ids
