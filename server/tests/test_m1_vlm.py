import asyncio
import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.llm import LlmError
from app.main import create_app
from app.storage import Store
from app.vlm import compress_image, normalize_series
from scripts.seed_demo import DEMO_RECORD_IMAGE, build_demo_objects, main as seed


def test_normalize_series_maps_model_variants():
    assert normalize_series("样品：碱灰") == "sample:碱灰"   # 全角冒号（glm-4.5v 实测输出）
    assert normalize_series("样品: 碱灰") == "sample:碱灰"
    assert normalize_series("标定") == "std"
    assert normalize_series("sample：碱灰") == "sample:碱灰"
    assert normalize_series("qc:标准物质") == "qc:crm"
    assert normalize_series("std") == "std"
    assert normalize_series("") == ""


DETECT_OK = '{"tables":[{"bbox":[10,100,990,300]},{"bbox":[10,450,990,800]}]}'
REGION_STD = '[{"series":"标定","values":{"m":0.1549,"V":28.54},"confidence":{"V":0.9}}]'
REGION_SAMPLE = '[{"series":"样品：碱灰","values":{"V":29.55,"ms":1.5919},"confidence":{"V":0.99}}]'


def test_two_stage_split_tables_and_merge_rows(monkeypatch):
    """版面分析返回两张表 → 逐表识别 → 行合并、series 归一、id 重排。"""
    calls = []

    async def fake_chat(messages, model=None, temperature=0.2, timeout=60):
        calls.append(messages[0]["content"][:6])
        if len(calls) == 1:
            return DETECT_OK                       # 第一段：版面分析
        return REGION_STD if len(calls) == 2 else REGION_SAMPLE
    monkeypatch.setattr("app.vlm.chat", fake_chat)

    _, ctx = build_demo_objects()
    from app.vlm import recognize_record
    ds = asyncio.run(recognize_record(_png_bytes(400, 600), ctx))
    assert len(calls) == 3                         # 1 次找表 + 2 次逐表
    assert [r["id"] for r in ds["rows"]] == ["p1", "p2"]
    assert [r["series"] for r in ds["rows"]] == ["std", "sample:碱灰"]
    assert ds["rows"][1]["values"]["ms"] == 1.5919


def test_layout_failure_falls_back_to_whole_page(monkeypatch):
    calls = []

    async def fake_chat(messages, model=None, temperature=0.2, timeout=60):
        calls.append(1)
        if len(calls) == 1:
            raise LlmError("NETWORK", "版面分析失败")
        return REGION_STD                          # 回退后整页识别
    monkeypatch.setattr("app.vlm.chat", fake_chat)

    _, ctx = build_demo_objects()
    from app.vlm import recognize_record
    ds = asyncio.run(recognize_record(_png_bytes(400, 600), ctx))
    assert len(calls) == 2
    assert [r["series"] for r in ds["rows"]] == ["std"]

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
