"""0.7.0 滴定曲线与误差预算的对账测试。

对账目标来自契约 0.7.0 示例（docs/contracts.md「滴定公式」与 AnalysisResult 节）：
v_eq 30.67 mL、pH_eq 3.97、变色窗 ΔV[-0.15, +0.46]、p2 ΔV -0.649 / pH 4.96、
误差预算 0.0015 / 实测 0.013114 / 比率 8.7。
"""

import pytest

from app.models.titration import convert_literature_curve
from app.services.analyze import analyze
from scripts.seed_demo import build_demo_objects


@pytest.fixture()
def demo_result():
    mine, ctx = build_demo_objects()
    return analyze(ctx, mine, {})


def test_curve_matches_contract_targets(demo_result):
    curve = demo_result["titration_curve"]
    assert curve["basis"]["point_id"] == "p3"          # 称样量居中的一份
    assert curve["basis"]["v_eq_ml"] == pytest.approx(30.67, abs=0.01)
    assert curve["ph_eq"] == pytest.approx(3.97, abs=0.01)
    w = curve["indicator"]["dv_window_ml"]
    assert w[0] == pytest.approx(-0.15, abs=0.02)      # pH 4.4 处
    assert w[1] == pytest.approx(0.46, abs=0.02)       # pH 3.1 处
    assert len(curve["theory"]) == 161                 # ΔV -2～+2，步长 0.025
    by_id = {e["point_id"]: e for e in curve["endpoints"]}
    assert set(by_id) == {"p1", "p2", "p3"}
    assert by_id["p2"]["dv_ml"] == pytest.approx(-0.649, abs=0.002)
    assert by_id["p2"]["ph"] == pytest.approx(4.96, abs=0.06)
    assert by_id["p1"]["dv_ml"] == pytest.approx(0.089, abs=0.002)


def test_error_budget_matches_contract(demo_result):
    b = demo_result["error_budget"]
    assert b["expected_rel_dev"] == pytest.approx(0.0015, abs=0.0001)
    assert b["observed_rel_dev"] == pytest.approx(0.013114, abs=1e-4)
    assert b["ratio"] == pytest.approx(8.7, abs=0.2)
    sources = {(i["source"], i["subject"]["point_id"]) for i in b["items"]}
    assert ("天平两次称量", "p1") in sources and ("滴定管两次读数", "p2") in sources


def test_literature_curve_converted_to_delta_v(demo_result):
    curve = demo_result["titration_curve"]
    ref_ds = {"id": "ds_lit_02", "rows": [
        {"values": {"V_lit": 28.5, "ph": 5.4}},
        {"values": {"V_lit": 30.0, "ph": 3.9}},      # 文献计量点 → ΔV 0
        {"values": {"V_lit": 31.5, "ph": 2.9}},
    ]}
    decl = {"columns": {"titrant_volume": "V_lit", "ph": "ph"},
            "meta": {"v_eq_ml": 30.0}, "space": "raw"}
    lit = convert_literature_curve(ref_ds, decl, curve)
    v_eq = curve["basis"]["v_eq_ml"]
    xs = [p["x"] for p in lit["points"]]
    assert xs[1] == pytest.approx(0.0, abs=0.01)
    assert xs[0] == pytest.approx(-1.5 * v_eq / 30.0, abs=0.02)
    assert xs[2] == pytest.approx(1.5 * v_eq / 30.0, abs=0.02)

    decl_pct = {"columns": {"titrant_volume": "a_pct", "ph": "ph"},
                "meta": {}, "space": "transformed"}
    ref_pct = {"id": "ds_lit_03", "rows": [
        {"values": {"a_pct": 95.0, "ph": 5.1}},
        {"values": {"a_pct": 100.0, "ph": 3.9}},
        {"values": {"a_pct": 105.0, "ph": 2.8}},
    ]}
    lit2 = convert_literature_curve(ref_pct, decl_pct, curve)
    xs2 = [p["x"] for p in lit2["points"]]
    assert xs2[1] == pytest.approx(0.0, abs=0.01)
    assert xs2[0] == pytest.approx(-0.05 * v_eq, abs=0.02)
    assert lit2["points"][1]["y"] == pytest.approx(3.9)


def test_sections_absent_without_constants(demo_result):
    """model_params 去掉 pka/误差常数时，两节都不输出。"""
    mine, ctx = build_demo_objects()
    for k in ("pka1", "pka2", "balance_error_g", "burette_error_ml"):
        ctx["model_params"].pop(k)
    r = analyze(ctx, mine, {})
    assert "titration_curve" not in r and "error_budget" not in r


def test_titration_with_literature_reference_does_not_crash(demo_result):
    """回归：上下文挂了文献参照时 _analyze_titration 曾因缺 ref_datasets 参数 NameError→500。"""
    mine, ctx = build_demo_objects()
    lit = {
        "schema_version": "0.8.0", "id": "ds_lit_curve", "source": "literature",
        "meta": {"title": "HCl 滴定 Na₂CO₃ 曲线", "doi": "10.xxxx/x", "figure": "图 2"},
        "columns": [{"key": "V_lit", "name": "V(HCl)", "unit": "mL"},
                    {"key": "ph", "name": "pH", "unit": ""}],
        "rows": [{"id": f"L{i}", "series": "std", "values": {"V_lit": v, "ph": p}}
                 for i, (v, p) in enumerate([(28.5, 5.4), (30.0, 3.9), (31.5, 2.9)], start=1)],
    }
    ctx["reference"]["datasets"] = [{
        "dataset_id": lit["id"],
        "columns": {"titrant_volume": "V_lit", "ph": "ph"},
        "meta": {"v_eq_ml": 30.0}, "space": "raw",
    }]
    r = analyze(ctx, mine, {lit["id"]: lit})       # 修复前这里直接 NameError
    curve = r["titration_curve"]
    assert len(curve["literature"]) == 1
    xs = [p["x"] for p in curve["literature"][0]["points"]]
    assert xs[1] == pytest.approx(0.0, abs=0.01)   # 文献计量点换算后落在 ΔV=0
