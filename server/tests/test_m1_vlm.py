import io

from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.main import create_app
from app.storage import Store
from app.vlm import compress_image
from scripts.seed_demo import main as seed

FAKE_DS = {
    "schema_version": "0.3.0",
    "source": "my_experiment",
    "meta": {"title": "识别结果"},
    "columns": [
        {"key": "c", "name": "c", "unit": "mg/L"},
        {"key": "A", "name": "A", "unit": ""},
        {"key": "V", "name": "V", "unit": "mL"},
        {"key": "dil", "name": "dil", "unit": ""},
    ],
    "rows": [
        {"id": "p1", "series": "std", "values": {"c": 0.10, "A": 0.041},
         "confidence": {"c": 0.9, "A": 0.85}, "verified": False},
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
