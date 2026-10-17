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
    assert c.get("/api/health").json()["contract_version"] == "0.4.0"
    templates = c.get("/api/m3/templates").json()
    ids = {t["id"] for t in templates}
    assert {"tpl_ammonia_nessler", "tpl_iodine_clock"} <= ids


def test_full_loop_analyze_findings_simulate_export(tmp_path):
    c = make_client(tmp_path)
    r = c.post("/api/m4/analyze", json={"context_id": "ctx_demo"})
    assert r.status_code == 200
    result = r.json()
    assert result["fits"][0]["slope"] > 0.4
    assert result["comparison"]["vs_limit"][0]["verdict"] in ("exceed", "comply")

    r = c.post("/api/m5/findings", json={"context_id": "ctx_demo"})
    assert r.status_code == 200
    assert "event: finding" in r.text and "event: done" in r.text

    r = c.post("/api/m6/simulate", json={
        "context_id": "ctx_demo", "finding_id": "f_conc1",
        "param": "dilution_factor", "frm": 1, "to": 10})
    assert r.status_code == 200
    assert len(r.json()["curve"]) == 20

    r = c.post("/api/m7/export", json={"context_id": "ctx_demo", "format": "md"})
    assert r.status_code == 200
    assert "标准曲线" in r.text


def test_create_context_from_template_and_put_dataset(tmp_path):
    c = make_client(tmp_path)
    r = c.post("/api/m3/contexts", json={"template_id": "tpl_ammonia_nessler"})
    assert r.status_code == 201
    ctx_id = r.json()["id"]

    ds = c.get("/api/datasets/ds_mine_demo").json()
    ds["rows"][0]["verified"] = True
    r = c.put("/api/datasets/ds_mine_demo", json=ds)
    assert r.status_code == 200
    assert r.json()["rows"][0]["verified"] is True

    bad = c.put("/api/datasets/ds_mine_demo", json={"no": "columns"})
    assert bad.status_code == 400


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
    assert snap["schema_version"] == "0.4.0"
    assert {s["id"] for s in snap["datasets"]} >= {"ds_mine_demo", "ds_lit_dxhx"}
    assert snap["analysis"]["fits"] and snap["findings"]

    miss = c.get("/api/snapshot/nope")
    assert miss.status_code == 404
