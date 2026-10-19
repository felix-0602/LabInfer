import base64

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.storage import Store
from scripts.seed_demo import main as seed


def make_client(tmp_path):
    store = Store(tmp_path)
    seed(store)
    return TestClient(create_app(store))


def test_health_and_templates(tmp_path):
    c = make_client(tmp_path)
    assert c.get("/api/health").json()["contract_version"] == "0.8.0"
    templates = c.get("/api/m3/templates").json()
    ids = {t["id"] for t in templates}
    assert {"tpl_alkali_titration", "tpl_iodine_clock"} <= ids
    demo = next(t for t in templates if t["id"] == "tpl_alkali_titration")
    assert demo["status"] == "演示"
    assert demo["model"] == "titration_standardization"


def test_full_loop_analyze_findings_simulate_export(tmp_path):
    c = make_client(tmp_path)
    r = c.post("/api/m4/analyze", json={"context_id": "ctx_demo"})
    assert r.status_code == 200
    result = r.json()
    assert result["fits"][0]["derived"]["c_hcl"] == pytest.approx(0.1027, abs=0.0002)
    assert result["comparison"]["vs_limit"][0]["verdict"] == "exceed"

    r = c.post("/api/m5/findings", json={"context_id": "ctx_demo"})
    assert r.status_code == 200
    assert "event: finding" in r.text and "event: done" in r.text
    assert "总碱度" in r.text

    r = c.post("/api/m6/simulate", json={
        "context_id": "ctx_demo", "finding_id": "f_worst",
        "param": "titrant_volume_delta", "from": -2, "to": 0, "unit": "mL"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["curve"]) == 20
    # 少滴 2 mL：62.58 × (31.29−2)/31.29 ≈ 58.58
    assert body["curve"][0]["y"] == pytest.approx(58.58, abs=0.05)

    r = c.post("/api/m7/export", json={"context_id": "ctx_demo", "format": "md"})
    assert r.status_code == 200
    assert "HCl 标定" in r.text and "总碱度" in r.text


def test_create_context_from_template_and_put_dataset(tmp_path):
    c = make_client(tmp_path)
    r = c.post("/api/m3/contexts", json={"template_id": "tpl_alkali_titration"})
    assert r.status_code == 201
    ctx_id = r.json()["id"]

    ds = c.get("/api/datasets/ds_mine_demo").json()
    ds["rows"][0]["verified"] = True
    r = c.put("/api/datasets/ds_mine_demo", json=ds)
    assert r.status_code == 200
    assert r.json()["rows"][0]["verified"] is True

    bad = c.put("/api/datasets/ds_mine_demo", json={"no": "columns"})
    assert bad.status_code == 400
    assert ctx_id


def test_context_carries_guide(tmp_path):
    """教学导读层（0.8.0 可选字段）随模板实例化透传，01/03 页与 M5 提示词都读它。"""
    c = make_client(tmp_path)
    r = c.get("/api/m3/contexts/ctx_demo")
    assert r.status_code == 200
    guide = r.json()["guide"]
    assert guide["status"] == "reviewed" and guide["audience_level"] == 3
    terms = {g["term"] for g in guide["glossary"]}
    assert {"标定", "基准物质", "总碱度", "系统误差"} <= terms
    assert all(g["term_id"] and g["plain"] for g in guide["glossary"])
    sections = {s["section_id"]: s for s in guide["sections"]}
    assert {"overview", "indicator", "precision", "thinking"} <= set(sections)
    assert sections["overview"]["show_in"] == ["context", "literature"]
    lit = [s for s in guide["sections"] if "literature" in s["show_in"]]
    assert 1 <= len(lit) <= 3                       # 03 页 1～3 节（M8 约定）
    assert len([s for s in guide["sections"] if "context" in s["show_in"]]) <= 8
    for s in sections.values():
        assert s["summary"] and s["body"] and s["sources"]
    src_ids = {s["source_id"] for s in guide["sources"]}
    assert all(set(s["sources"]) <= src_ids for s in sections.values())
    assert "model_params.molar_mass_na2co3_g_mol" in guide["field_notes"]
    # 待核出处不整节消失，只按 verified 降级显示（src_gb601_boil）
    boil = next(s for s in guide["sources"] if s["source_id"] == "src_gb601_boil")
    assert boil["verified"] is False
    # 模板列表标「有导读」
    tpl = next(t for t in c.get("/api/m3/templates").json()
               if t["id"] == "tpl_alkali_titration")
    assert tpl["has_guide"] is True


def test_guide_structure_consistency(tmp_path):
    """guide 内部索引自洽（M8 渲染前提）：term 链接、source 引用、长度与页面节数。"""
    import re
    c = make_client(tmp_path)
    guide = c.get("/api/m3/contexts/ctx_demo").json()["guide"]
    term_ids = {g["term_id"] for g in guide["glossary"]}
    src_ids = {s["source_id"] for s in guide["sources"]}

    for s in guide["sections"]:
        linked = set(re.findall(r"\]\(term:([a-z_]+)\)", s["body"]))
        assert linked <= term_ids, f"{s['section_id']} 链接了未登记术语: {linked - term_ids}"
        assert set(s["sources"]) <= src_ids
        assert 0 < len(s["summary"]) <= 50
        assert len(s["body"]) >= 150                    # 不设 300 下限：说清即止，防为凑字注水
        assert set(s["terms"]) <= term_ids
        assert set(s["show_in"]) <= {"context", "literature"}
    for g in guide["glossary"]:
        assert g["source"] in src_ids
        assert 0 < len(g["plain"]) <= 60
    for note in guide["field_notes"].values():
        assert 0 < len(note["label"]) <= 16
        assert 0 < len(note["plain"]) <= 60
        if note.get("term_id"):
            assert note["term_id"] in term_ids
    ctx_n = len([s for s in guide["sections"] if "context" in s["show_in"]])
    lit_n = len([s for s in guide["sections"] if "literature" in s["show_in"]])
    assert 4 <= ctx_n <= 8 and 1 <= lit_n <= 3          # M8 约定的页面容量


def test_m1_without_cache_returns_503(tmp_path):
    import io
    c = make_client(tmp_path)
    r = c.post(
        "/api/m1/records",
        data={"context_id": "ctx_demo"},
        files={"image": ("note.jpg", io.BytesIO(b"fake-image-bytes"), "image/jpeg")},
    )
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "VLM_UNAVAILABLE"


def test_export_docx(tmp_path):
    c = make_client(tmp_path)
    c.post("/api/m4/analyze", json={"context_id": "ctx_demo"})
    c.post("/api/m5/findings", json={"context_id": "ctx_demo"})
    r = c.post("/api/m7/export", json={"context_id": "ctx_demo", "format": "docx"})
    assert r.status_code == 200
    assert r.content[:2] == b"PK"
    assert "msword" in r.headers["content-type"] or "wordprocessingml" in r.headers["content-type"]


def test_snapshot_full_chain(tmp_path):
    c = make_client(tmp_path)
    c.post("/api/m4/analyze", json={"context_id": "ctx_demo"})
    c.post("/api/m5/findings", json={"context_id": "ctx_demo"})
    r = c.get("/api/snapshot/ctx_demo")
    assert r.status_code == 200
    snap = r.json()
    assert snap["schema_version"] == "0.8.0"
    assert {s["id"] for s in snap["datasets"]} == {"ds_mine_demo"}
    assert snap["analysis"]["fits"] and snap["findings"]
    assert "titration_curve" in snap["analysis"] and "error_budget" in snap["analysis"]

    miss = c.get("/api/snapshot/nope")
    assert miss.status_code == 404


def test_export_png_and_include_flags(tmp_path):
    c = make_client(tmp_path)
    c.post("/api/m4/analyze", json={"context_id": "ctx_demo"})
    c.post("/api/m5/findings", json={"context_id": "ctx_demo"})

    r = c.post("/api/m7/export", json={"context_id": "ctx_demo", "format": "png"})
    assert r.status_code == 200
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert r.headers["content-type"] == "image/png"

    r = c.post("/api/m7/export", json={
        "context_id": "ctx_demo", "format": "md",
        "include": {"figure": False, "anomalies": False,
                    "quality_control": False, "sources": False}})
    assert r.status_code == 200
    assert "质量控制" not in r.text and "参照来源" not in r.text
    assert "## 滴定曲线" not in r.text                   # figure=False 连小节一起关
    assert "仪器误差预算" not in r.text                    # anomaly 类结论被过滤
    assert "总碱度" in r.text                             # conclusion 类保留

    r = c.post("/api/m7/export", json={
        "context_id": "ctx_demo", "format": "md", "include": {"figure": True}})
    assert r.status_code == 200 and "## 滴定曲线" in r.text and "变色窗" in r.text


def test_export_md_embeds_figure_data_uri(tmp_path):
    """md 导出的插图必须自包含：data URI 内嵌，而不是指向不存在的 figure.png。"""
    c = make_client(tmp_path)
    c.post("/api/m4/analyze", json={"context_id": "ctx_demo"})
    c.post("/api/m5/findings", json={"context_id": "ctx_demo"})

    r = c.post("/api/m7/export", json={"context_id": "ctx_demo", "format": "md"})
    assert r.status_code == 200
    assert "](figure.png)" not in r.text
    uri_at = r.text.find("data:image/png;base64,")
    assert uri_at != -1
    payload = r.text[uri_at:].split(")", 1)[0][len("data:image/png;base64,"):]
    assert base64.b64decode(payload)[:8] == b"\x89PNG\r\n\x1a\n"   # 内嵌的是合法 PNG

    off = c.post("/api/m7/export", json={
        "context_id": "ctx_demo", "format": "md", "include": {"figure": False}})
    assert off.status_code == 200
    assert "data:image/png;base64," not in off.text and "![图" not in off.text


def test_simulate_co2_retention(tmp_path):
    c = make_client(tmp_path)
    c.post("/api/m4/analyze", json={"context_id": "ctx_demo"})
    r = c.post("/api/m6/simulate", json={
        "context_id": "ctx_demo", "finding_id": "f", "from": 0, "to": 1,
        "param": "co2_retained_fraction"})
    assert r.status_code == 200
    body = r.json()
    assert body["predicted"]["co2_retained_fraction"] == 0.5
    assert 3.97 < body["predicted"]["ph_eq"] < 8.0       # 驱除 CO₂ 后计量点 pH 上移
    assert len(body["curve"]) == 161


def test_m5_co2_entry_and_ladder(tmp_path):
    """煮沸滑块的入口：模板结论带 co2_retained_fraction 推演；讲解阶梯按 wiki 规则挂接。"""
    import json as _json

    c = make_client(tmp_path)
    c.post("/api/m4/analyze", json={"context_id": "ctx_demo"})
    r = c.post("/api/m5/findings", json={"context_id": "ctx_demo"})
    assert r.status_code == 200
    items = []
    for line in r.text.splitlines():
        if line.startswith("data: ") and '"id"' in line:
            items.append(_json.loads(line[len("data: "):]))

    co2 = next(f for f in items if f["id"] == "f_co2")
    assert co2["simulatable"] is True
    assert co2["simulation"]["param"] == "co2_retained_fraction"
    assert co2["simulation"]["from"] == 0 and co2["simulation"]["to"] == 1

    # 锚点 titration_curve：往上递最低两级（4、6 级）；「待核」级不进演示
    curve_f = next(f for f in items if f["id"] == "f_curve")
    assert [rung["rung_id"] for rung in curve_f["ladder"]] == \
        ["L4-indicator", "L6-endpoint-error"]
    budget_f = next(f for f in items if f["id"] == "f_budget")
    assert [rung["rung_id"] for rung in budget_f["ladder"]] == ["L6-budget"]
    assert "L4-co2" not in r.text and "L7-gb601" not in r.text
    # 锚点未命中 evidence 的结论不挂阶梯
    worst_f = next(f for f in items if f["id"] == "f_worst")
    assert "ladder" not in worst_f


CUSTOM_TPL = {
    "name": "混合碱总碱度（自定义模板示例）",
    "purpose": "以 HCl 滴定混合碱，测总碱度",
    "model": "titration_standardization",
    "model_params": {"molar_mass_na2co3_g_mol": 105.99, "molar_mass_na2o_g_mol": 61.979,
                     "stock_volume_ml": 250, "aliquot_volume_ml": 25},
    "variables": {"columns": [
        {"key": "m", "role": "mass", "unit": "g"},
        {"key": "V", "role": "volume", "unit": "mL"},
        {"key": "ms", "role": "sample_mass", "unit": "g", "optional": True},
    ]},
    "reference": {"datasets": [], "crm": None, "limits": []},
    "qc_rules": [{"rule_id": "parallel_rpd", "params": {"max": 0.002},
                  "citation": "分析化学实验平行测定要求"}],
}


def test_template_library_create_and_instantiate(tmp_path):
    c = make_client(tmp_path)
    r = c.post("/api/m3/templates", json=CUSTOM_TPL)
    assert r.status_code == 201
    tpl = r.json()
    assert tpl["status"] == "自定义" and tpl["id"].startswith("tpl_")
    assert "datasets" not in tpl                      # 模板不含数据

    listed = {t["id"]: t for t in c.get("/api/m3/templates").json()}
    assert tpl["id"] in listed and listed[tpl["id"]]["status"] == "自定义"

    r = c.post("/api/m3/contexts", json={"template_id": tpl["id"]})
    assert r.status_code == 201
    ctx = r.json()
    assert ctx["model"] == "titration_standardization"
    assert ctx["datasets"] == {"mine": None}

    dup = c.post("/api/m3/templates", json={**CUSTOM_TPL, "id": "tpl_alkali_titration"})
    assert dup.status_code == 409
    bad_model = c.post("/api/m3/templates", json={**CUSTOM_TPL, "model": "nope"})
    assert bad_model.status_code == 400
    no_role = c.post("/api/m3/templates", json={
        **CUSTOM_TPL, "variables": {"columns": [{"key": "m", "role": "mass", "unit": "g"}]}})
    assert no_role.status_code == 400


def test_full_loop_on_sqlite_backend(tmp_path):
    """SQLite 后端跑通与 JSON 后端相同的闭环（docs/sql.md 的双后端承诺）。"""
    from app.sqlstore import SqlStore
    store = SqlStore(tmp_path / "e2e.sqlite3")
    seed(store)
    c = TestClient(create_app(store))

    r = c.post("/api/m4/analyze", json={"context_id": "ctx_demo"})
    assert r.status_code == 200
    assert r.json()["fits"][0]["derived"]["c_hcl"] == pytest.approx(0.1027, abs=0.0002)

    r = c.post("/api/m5/findings", json={"context_id": "ctx_demo"})
    assert r.status_code == 200 and "event: finding" in r.text

    r = c.get("/api/snapshot/ctx_demo")
    assert r.status_code == 200
    assert r.json()["schema_version"] == "0.8.0"
