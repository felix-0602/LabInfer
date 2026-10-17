import io

from fastapi.testclient import TestClient

from app.config import settings
from app.llm import LlmError
from app.main import create_app
from app.storage import Store
from scripts.seed_demo import main as seed

GOOD = ("线性关系显著。\n"
        '[{"type":"conclusion","text":"地表水样品浓度 2.781 mg/L，超 III 类限值 1 mg/L。",'
        '"evidence":[{"type":"point","dataset_id":"ds_mine_demo","point_id":"s1a"},'
        '{"type":"comparison","target":"vs_limit[0]"}]}]')
BAD = '[{"type":"pattern","text":"活化能高达 99.9，非常大。","evidence":[{"type":"fit","dataset_id":"ds_mine_demo"}]}]'


def make_client(tmp_path):
    store = Store(tmp_path)
    seed(store)
    client = TestClient(create_app(store))
    r = client.post("/api/m4/analyze", json={"context_id": "ctx_demo"})
    assert r.status_code == 200
    return client


def _enable_llm(monkeypatch):
    monkeypatch.setattr(settings, "glm_base_url", "https://api.example.com")
    monkeypatch.setattr(settings, "glm_api_key", "test-key")


def test_llm_valid_finding_kept(tmp_path, monkeypatch):
    client = make_client(tmp_path)
    _enable_llm(monkeypatch)
    async def fake_chat(messages, model=None, temperature=0.2):
        return GOOD
    monkeypatch.setattr("app.prompts.chat", fake_chat)
    r = client.post("/api/m5/findings", json={"context_id": "ctx_demo"})
    assert r.status_code == 200
    assert "地表水样品浓度" in r.text


def test_llm_retry_after_all_invalid(tmp_path, monkeypatch):
    client = make_client(tmp_path)
    _enable_llm(monkeypatch)
    calls = []

    async def fake_chat(messages, model=None, temperature=0.2):
        calls.append(len(messages))
        return BAD if len(calls) == 1 else GOOD
    monkeypatch.setattr("app.prompts.chat", fake_chat)
    r = client.post("/api/m5/findings", json={"context_id": "ctx_demo"})
    assert r.status_code == 200
    assert "地表水样品浓度" in r.text
    assert len(calls) == 2 and calls[1] > calls[0]


def test_llm_error_falls_back_to_template(tmp_path, monkeypatch):
    client = make_client(tmp_path)
    _enable_llm(monkeypatch)

    async def fake_chat(messages, model=None, temperature=0.2):
        raise LlmError("NETWORK", "网络错误")
    monkeypatch.setattr("app.prompts.chat", fake_chat)
    r = client.post("/api/m5/findings", json={"context_id": "ctx_demo"})
    assert r.status_code == 200
    assert "标准曲线线性良好" in r.text


def test_no_llm_configured_uses_template(tmp_path):
    client = make_client(tmp_path)
    r = client.post("/api/m5/findings", json={"context_id": "ctx_demo"})
    assert r.status_code == 200
    assert "event: finding" in r.text
