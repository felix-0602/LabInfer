from app.storage import Store


def test_roundtrip_and_atomic(tmp_path):
    s = Store(tmp_path)
    ds = {"columns": [{"key": "c"}], "rows": []}
    out = s.put_dataset(ds)
    assert out["id"].startswith("ds_")
    got = s.get_dataset(out["id"])
    assert got["columns"] == ds["columns"]
    assert list((tmp_path / "datasets").glob("*.json"))


def test_rejects_path_injection(tmp_path):
    s = Store(tmp_path)
    import pytest
    with pytest.raises(ValueError):
        s.get("datasets", "../evil")
