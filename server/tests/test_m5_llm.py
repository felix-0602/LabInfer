import asyncio
import io
import time

from fastapi.testclient import TestClient

from app.config import settings
from app.llm import LlmError
from app.main import create_app
from app.storage import Store
from scripts.seed_demo import main as seed

GOOD = ("标定线性良好。\n"
        '[{"type":"conclusion","text":"碱灰平行 2（s2）总碱度 62.578%，高于纯 Na₂CO₃ 理论值 58.47%。",'
        '"evidence":[{"type":"point","dataset_id":"ds_mine_demo","point_id":"s2"},'
        '{"type":"comparison","target":"vs_limit[1]"}]}]')
BAD = '[{"type":"pattern","text":"活化能高达 99.9，非常大。","evidence":[{"type":"fit","dataset_id":"ds_mine_demo"}]}]'


def make_client(tmp_path):
    import app.cache as cache_mod
    cache_mod.RUNTIME_CACHE_DIR = tmp_path / "rt"   # m5 结论缓存按用例隔离，防跨用例/跨运行串缓存
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
    async def fake_chat(messages, model=None, temperature=0.2, timeout=60):
        return GOOD
    monkeypatch.setattr("app.prompts.chat", fake_chat)
    r = client.post("/api/m5/findings", json={"context_id": "ctx_demo"})
    assert r.status_code == 200
    assert "碱灰平行 2" in r.text


def test_llm_retry_after_all_invalid(tmp_path, monkeypatch):
    client = make_client(tmp_path)
    _enable_llm(monkeypatch)
    calls = []

    async def fake_chat(messages, model=None, temperature=0.2, timeout=60):
        calls.append(len(messages))
        return BAD if len(calls) == 1 else GOOD
    monkeypatch.setattr("app.prompts.chat", fake_chat)
    r = client.post("/api/m5/findings", json={"context_id": "ctx_demo"})
    assert r.status_code == 200
    assert "碱灰平行 2" in r.text
    assert len(calls) == 2 and calls[1] > calls[0]


def test_llm_error_falls_back_to_template(tmp_path, monkeypatch):
    client = make_client(tmp_path)
    _enable_llm(monkeypatch)

    async def fake_chat(messages, model=None, temperature=0.2, timeout=60):
        raise LlmError("NETWORK", "网络错误")
    monkeypatch.setattr("app.prompts.chat", fake_chat)
    r = client.post("/api/m5/findings", json={"context_id": "ctx_demo"})
    assert r.status_code == 200
    assert "整齐落在" in r.text


def test_llm_unknown_term_mark_stripped(tmp_path, monkeypatch):
    """term 标记只许指向 ctx 术语表；未知的在校验器剥成纯文字，不进结果。"""
    client = make_client(tmp_path)
    _enable_llm(monkeypatch)
    payload = ('好。\n'
               '[{"type":"conclusion",'
               '"text":"碱灰平行 2（s2）总碱度 62.578%，高于纯 Na₂CO₃ 理论值 58.47%，'
               '见[说法](term:made_up_id)。",'
               '"evidence":[{"type":"point","dataset_id":"ds_mine_demo","point_id":"s2"},'
               '{"type":"comparison","target":"vs_limit[1]"}]}]')

    async def fake_chat(messages, model=None, temperature=0.2, timeout=60):
        return payload
    monkeypatch.setattr("app.prompts.chat", fake_chat)
    r = client.post("/api/m5/findings", json={"context_id": "ctx_demo"})
    assert r.status_code == 200
    assert "(term:made_up_id)" not in r.text
    assert "见说法。" in r.text


def test_llm_confidence_95_allowed_with_u95(tmp_path, monkeypatch):
    """置信水平 95% 是 u95 的方法常数：分析带不确定度时正文可写（行业规范写法）。"""
    client = make_client(tmp_path)
    _enable_llm(monkeypatch)
    payload = ('好。\n'
               '[{"type":"conclusion",'
               '"text":"碱灰平行 2（s2）总碱度 62.578%，高于纯 Na₂CO₃ 理论值 58.47%，'
               '报告为 62.578 ± 0.4，95% 置信。",'
               '"evidence":[{"type":"point","dataset_id":"ds_mine_demo","point_id":"s2"},'
               '{"type":"comparison","target":"vs_limit[1]"}]}]')

    async def fake_chat(messages, model=None, temperature=0.2, timeout=60):
        return payload
    monkeypatch.setattr("app.prompts.chat", fake_chat)
    r = client.post("/api/m5/findings", json={"context_id": "ctx_demo"})
    assert r.status_code == 200
    assert "95% 置信" in r.text          # 未因数字无溯源被剔


def test_llm_num_mark_full_value_checked(tmp_path, monkeypatch):
    """num 标记里的全精度同样过数字溯源：伪造原值的整条剔除，有效的保留。"""
    client = make_client(tmp_path)
    _enable_llm(monkeypatch)
    payload = ('好。\n'
               '[{"type":"conclusion",'
               '"text":"碱灰平行 2（s2）总碱度 [62.58](num:99.99)%，高于纯 Na₂CO₃ 理论值 58.47%。",'
               '"evidence":[{"type":"point","dataset_id":"ds_mine_demo","point_id":"s2"},'
               '{"type":"comparison","target":"vs_limit[1]"}]},'
               '{"type":"pattern","text":"拟合 R²=[0.9998](num:0.99976)。",'
               '"evidence":[{"type":"fit","dataset_id":"ds_mine_demo"}]}]')

    async def fake_chat(messages, model=None, temperature=0.2, timeout=60):
        return payload
    monkeypatch.setattr("app.prompts.chat", fake_chat)
    r = client.post("/api/m5/findings", json={"context_id": "ctx_demo"})
    assert r.status_code == 200
    assert "(num:99.99)" not in r.text       # 伪造原值（偏离真值超容差）：整条被剔
    assert "(num:0.99976)" in r.text        # 真原值：保留


def test_no_llm_configured_uses_template(tmp_path):
    client = make_client(tmp_path)
    r = client.post("/api/m5/findings", json={"context_id": "ctx_demo"})
    assert r.status_code == 200
    assert "event: finding" in r.text


def test_llm_findings_cached_on_second_call(tmp_path, monkeypatch):
    """结论缓存：同 ctx 同分析第二次调用不再出网（glm-5.3 一次生成可达数分钟，公网演示必须秒回）。"""
    client = make_client(tmp_path)
    _enable_llm(monkeypatch)
    calls = []

    async def fake_chat(messages, model=None, temperature=0.2, timeout=60):
        calls.append(1)
        return GOOD

    monkeypatch.setattr("app.prompts.chat", fake_chat)
    r1 = client.post("/api/m5/findings", json={"context_id": "ctx_demo"})
    r2 = client.post("/api/m5/findings", json={"context_id": "ctx_demo"})
    assert r1.status_code == r2.status_code == 200
    assert "碱灰平行 2" in r1.text and "碱灰平行 2" in r2.text
    assert len(calls) == 1                 # 第二次命中运行时缓存，不再调模型


def test_stream_starts_before_llm_finishes(tmp_path, monkeypatch):
    """公网链路会掐无字节的空闲连接：首字节（keepalive 心跳）必须先于 LLM 完成就到。
    TestClient 的 httpx 管道会缓冲整条流，这里直接裸调 ASGI 量每个 body chunk 的时刻。"""
    client = make_client(tmp_path)
    _enable_llm(monkeypatch)

    async def slow_chat(messages, model=None, temperature=0.2, timeout=60):
        await asyncio.sleep(0.5)
        return GOOD

    monkeypatch.setattr("app.prompts.chat", slow_chat)

    async def drive():
        t0 = time.monotonic()
        sent = []
        body_sent = False
        never = asyncio.Event()          # 真实服务器语义：body 发完后 receive 一直等到断开

        async def receive():
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": b'{"context_id": "ctx_demo"}',
                        "more_body": False}
            await never.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            if message["type"] == "http.response.body":
                sent.append((time.monotonic() - t0, message.get("body", b"")))

        scope = {"type": "http", "asgi": {"version": "2.0", "spec_version": "2.1"},
                 "http_version": "1.1", "method": "POST", "scheme": "http",
                 "path": "/api/m5/findings", "raw_path": b"/api/m5/findings",
                 "query_string": b"", "root_path": "",
                 "headers": [(b"content-type", b"application/json")],
                 "client": ("test", 1), "server": ("test", 80)}
        await client.app(scope, receive, send)
        return sent

    sent = asyncio.run(drive())
    t_first, body_first = sent[0]
    assert body_first.startswith(b":")            # 心跳注释行先到，不等 LLM
    assert t_first < 0.4
    assert sent[-1][0] >= 0.45                    # 结论在 LLM（0.5s）完成后才出
    tail = b"".join(b for _, b in sent)
    assert b"event: finding" in tail and b"event: done" in tail
    assert "碱灰平行 2".encode() in tail


def test_llm_prompt_carries_guide_glossary(tmp_path, monkeypatch):
    """表达标准（wiki.md#表达标准）：ctx 带 guide 时，术语表要进提示词。"""
    client = make_client(tmp_path)
    _enable_llm(monkeypatch)
    captured = {}

    async def fake_chat(messages, model=None, temperature=0.2, timeout=60):
        captured["user"] = messages[1]["content"]
        captured["system"] = messages[0]["content"]
        return GOOD
    monkeypatch.setattr("app.prompts.chat", fake_chat)
    r = client.post("/api/m5/findings", json={"context_id": "ctx_demo"})
    assert r.status_code == 200
    assert "标定（standardization）——拿一份纯到可以完全信任、能称出准确克数的固体，反过来测出一瓶溶液的真实浓度" in captured["user"]
    assert "帮助理解" in captured["user"]
    assert "语言标准" in captured["system"]
    assert "路标" in captured["system"]        # 节奏与路标规则（wiki.md#表达标准）
