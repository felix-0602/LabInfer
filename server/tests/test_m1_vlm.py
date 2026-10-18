import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.main import create_app
from app.storage import Store
from app.vlm import compress_image
from scripts.seed_demo import DEMO_RECORD_IMAGE, main as seed

FAKE_DS = {
    "schema_version": "0.5.0",
    "source": "my_experiment",
    "meta": {"title": "识别结果"},
    "columns": [
        {"key": "m", "name": "m", "unit": "g"},
        {"key": "V", "name": "V", "unit": "mL"},
        {"key": "ms", "name": "ms", "unit": "g"},
    ],
    "rows": [
        {"id": "p1", "series": "std", "values": {"m": 0.1549, "V": 28.54},
         "confidence": {"m": 0.9, "V": 0.62}, "verified": False},
    ],
}


def _png_bytes(w=2000, h=800):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_compress_image_limits_long_edge():
    out = compress_image(_png_bytes())
    img = Image.open(io.BytesIO(out))
    assert max(img.size) <= 1568


def test_m1_vlm_recognize_and_cache_bake(tmp_path, monkeypatch):
    store = Store(tmp_path)
    seed(store)
    client = TestClient(create_app(store))
    monkeypatch.setattr(settings, "glm_base_url", "https://api.example.com")
    monkeypatch.setattr(settings, "glm_api_key", "test-key")

    async def fake_recognize(data, ctx):
        return {k: v for k, v in FAKE_DS.items()}
    monkeypatch.setattr("app.routers.m1.recognize_record", fake_recognize)

    mem = {}

    def fake_cache_get(kind, key):
        return mem.get(key)

    def fake_cache_put(kind, key, payload):
        mem[key] = payload
    monkeypatch.setattr("app.routers.m1.cache_get", fake_cache_get)
    monkeypatch.setattr("app.routers.m1.cache_put", fake_cache_put)

    r = client.post("/api/m1/records", data={"context_id": "ctx_demo"},
                    files={"image": ("note.png", io.BytesIO(_png_bytes(64, 64)), "image/png")})
    assert r.status_code == 201
    ds = r.json()
    assert ds["rows"][0]["series"] == "std"
    assert "cached" not in ds
    assert len(mem) == 1
    ctx = store.get_context("ctx_demo")
    assert ctx["datasets"]["mine"] == ds["id"]

    r2 = client.post("/api/m1/records", data={"context_id": "ctx_demo"},
                     files={"image": ("note.png", io.BytesIO(_png_bytes(64, 64)), "image/png")})
    assert r2.status_code == 201
    assert r2.json().get("cached") is True


def test_m1_unconfigured_returns_503(tmp_path):
    store = Store(tmp_path)
    seed(store)
    client = TestClient(create_app(store))
    r = client.post("/api/m1/records", data={"context_id": "ctx_demo"},
                    files={"image": ("note.png", io.BytesIO(b"x"), "image/png")})
    assert r.status_code == 503


def test_m1_demo_record_photo_hits_baked_cache(tmp_path):
    """演示保底：上传真实数据记录页照片（DEMO-01.jpg），无需 VLM 即得种子数据。"""
    if not DEMO_RECORD_IMAGE.exists():
        import pytest
        pytest.skip("演示记录照片不存在（design/assets/DEMO-01.jpg）")
    store = Store(tmp_path)
    seed(store)
    client = TestClient(create_app(store))
    with open(DEMO_RECORD_IMAGE, "rb") as f:
        r = client.post(
            "/api/m1/records",
            data={"context_id": "ctx_demo"},
            files={"image": ("DEMO-01.jpg", f, "image/jpeg")},
        )
    assert r.status_code == 201
    ds = r.json()
    assert ds["cached"] is True
    assert len(ds["rows"]) == 6
    assert ds["rows"][0]["values"] == {"m": 0.1549, "V": 28.54}
    assert ds["rows"][0]["confidence"]["V"] < 0.7      # 涂改过的格子保留低置信，供 M8 校正
    ctx = store.get_context("ctx_demo")
    assert ctx["datasets"]["mine"] == ds["id"]
