"""SQLite 后端（app/sqlstore.py）与 JSON 后端的接口一致性、注入防护。"""

import json

from app.sqlstore import SqlStore


def make_store(tmp_path):
    return SqlStore(tmp_path / "t.sqlite3")


def _dataset(id, title="t"):
    return {"schema_version": "0.6.0", "id": id, "source": "my_experiment",
            "meta": {"title": title}, "columns": [], "rows": []}


def test_roundtrip_all_kinds(tmp_path):
    store = make_store(tmp_path)
    ds = _dataset("ds_1")
    assert store.put_dataset(ds) is ds
    assert store.get_dataset("ds_1")["meta"]["title"] == "t"
    assert store.get_dataset("nope") is None

    ctx = {"schema_version": "0.6.0", "id": "ctx_1", "name": "n", "model": "titration_standardization",
           "datasets": {"mine": "ds_1"}}
    store.put_context(ctx)
    assert store.get_context("ctx_1")["datasets"]["mine"] == "ds_1"

    analysis = {"schema_version": "0.6.0", "context_id": "ctx_1", "model": "titration_standardization",
                "fits": [{"derived": {"c_hcl": 0.102735}}]}
    store.put_analysis("ctx_1", analysis)
    assert store.get_analysis("ctx_1")["fits"][0]["derived"]["c_hcl"] == 0.102735

    findings = [{"id": "f1", "type": "pattern", "text": "a", "evidence": []},
                {"id": "f2", "type": "anomaly", "text": "b", "evidence": []}]
    store.put_findings("ctx_1", findings)
    assert [f["id"] for f in store.get_findings("ctx_1")] == ["f1", "f2"]
    assert store.get_findings("nope") is None


def test_findings_replace_keeps_only_latest(tmp_path):
    store = make_store(tmp_path)
    store.put_findings("ctx_1", [{"id": "f1", "type": "pattern", "text": "old", "evidence": []}])
    store.put_findings("ctx_1", [{"id": "f1", "type": "pattern", "text": "new", "evidence": []},
                                 {"id": "f2", "type": "anomaly", "text": "x", "evidence": []}])
    got = store.get_findings("ctx_1")
    assert len(got) == 2 and got[0]["text"] == "new"


def test_parameter_binding_neutralizes_hostile_ids(tmp_path):
    """id 里带 SQL 注入载荷也只是普通字符串，表结构不受影响。"""
    store = make_store(tmp_path)
    evil = "x'); DROP TABLE datasets;--"
    store.put_dataset(_dataset(evil))
    assert store.get_dataset(evil)["id"] == evil
    store.put_context({"id": "ctx_ok", "name": "n", "model": "titration_standardization",
                       "datasets": {"mine": None}})
    assert store.get_context("ctx_ok") is not None          # datasets 表仍在
    assert store.get_dataset(evil) is not None
    store.put_findings(evil, [{"id": "f1", "type": "pattern", "text": "t", "evidence": []}])
    assert store.get_findings(evil)[0]["id"] == "f1"


def test_upload_writes_file_beside_db(tmp_path):
    store = make_store(tmp_path)
    p = store.save_upload(b"hello", ".jpg")
    assert p.exists() and p.read_bytes() == b"hello"
    assert p.parent == tmp_path / "uploads"


def test_templates_roundtrip(tmp_path):
    store = make_store(tmp_path)
    tpl = {"id": "tpl_x", "schema_version": "0.6.0", "name": "n", "model": "arrhenius",
           "status": "自定义", "variables": {"columns": []}}
    store.put_template(tpl)
    assert store.get_template("tpl_x")["name"] == "n"
    assert [t["id"] for t in store.list_templates()] == ["tpl_x"]


def test_payload_preserves_unicode_and_nested_json(tmp_path):
    store = make_store(tmp_path)
    ds = _dataset("ds_2", title="碱灰总碱度（以 Na₂O 计）")
    ds["rows"] = [{"id": "p1", "series": "std", "values": {"m": 0.1549, "V": 28.54}}]
    store.put_dataset(ds)
    assert store.get_dataset("ds_2") == json.loads(json.dumps(ds, ensure_ascii=False))
