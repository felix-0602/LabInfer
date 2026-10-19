import pytest

import app.llm as llm_mod
from app.llm import OutboundError, validate_outbound_url


@pytest.mark.parametrize("url", [
    "http://api.example.com/v1/chat/completions",
    "https://localhost/v1/chat/completions",
    "https://127.0.0.1/v1/chat/completions",
    "https://192.168.1.1/v1/chat/completions",
    "https://10.0.0.5/v1/chat/completions",
    "https://[::1]/v1/chat/completions",
])
def test_rejects_non_public_or_plain_http(url):
    with pytest.raises(OutboundError):
        validate_outbound_url(url)


def test_chat_client_ignores_ambient_proxy_env(monkeypatch):
    """出网不读环境代理：shell 里的 socks:// 代理变量曾让 httpx 直接抛
    Unknown scheme for proxy URL。出网策略由 validate_outbound_url 全权管理。"""
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def __aenter__(self):
            raise RuntimeError("测试不出网")

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(llm_mod.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(llm_mod.settings, "glm_base_url", "https://api.example.com/v1")
    monkeypatch.setattr(llm_mod.settings, "glm_api_key", "k")
    monkeypatch.setattr(llm_mod.socket, "getaddrinfo", lambda *a, **k: [])
    import asyncio
    with pytest.raises(RuntimeError):
        asyncio.run(llm_mod.chat([{"role": "user", "content": "x"}]))
    assert captured.get("trust_env") is False


class _FakeStreamResp:
    def __init__(self, lines, status_code=200):
        self._lines = lines
        self.status_code = status_code

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeStreamClient:
    def __init__(self, lines, status_code=200, **kwargs):
        self._resp = _FakeStreamResp(lines, status_code)

    def stream(self, *args, **kwargs):
        outer = self

        class _Ctx:
            async def __aenter__(self):
                return outer._resp

            async def __aexit__(self, *exc):
                return False
        return _Ctx()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _fake_sse(monkeypatch, lines, status_code=200):
    monkeypatch.setattr(llm_mod.settings, "glm_base_url", "https://api.example.com/v1")
    monkeypatch.setattr(llm_mod.settings, "glm_api_key", "k")
    monkeypatch.setattr(llm_mod.socket, "getaddrinfo", lambda *a, **k: [])
    monkeypatch.setattr(llm_mod.httpx, "AsyncClient",
                        lambda **kwargs: _FakeStreamClient(lines, status_code, **kwargs))


def test_chat_streams_and_aggregates(monkeypatch):
    """流式拉取聚合成完整串：SSE 行 → deltas 拼接，接口与非流式等价。"""
    import asyncio
    lines = [
        'data: {"choices":[{"delta":{"role":"assistant"}}]}',
        "",
        ": keepalive",
        'data: {"choices":[{"delta":{"content":"总碱度"}}]}',
        'data: {"choices":[{"delta":{"content":"62.58%"}}]}',
        'data: {"choices":[{"delta":{}}]}',
        "data: [DONE]",
    ]
    _fake_sse(monkeypatch, lines)
    out = asyncio.run(llm_mod.chat([{"role": "user", "content": "x"}]))
    assert out == "总碱度62.58%"


def test_chat_maps_stream_status_errors(monkeypatch):
    import asyncio
    _fake_sse(monkeypatch, [], status_code=429)
    with pytest.raises(llm_mod.LlmError) as ei:
        asyncio.run(llm_mod.chat([{"role": "user", "content": "x"}]))
    assert ei.value.kind == "RATE_LIMIT"
