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
