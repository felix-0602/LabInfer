"""GLM 客户端骨架。安全约束：仅 https、拒绝环回/私网/保留地址（对齐项目级约束）。"""

import ipaddress
import os
import socket
from urllib.parse import urlparse

import httpx

from .config import settings


class OutboundError(ValueError):
    pass


class LlmError(RuntimeError):
    def __init__(self, kind: str, message: str, status: int | None = None):
        super().__init__(message)
        self.kind = kind
        self.status = status


# fake-ip 代理环境（TUN 模式）会把所有域名解析进 198.18.0.0/15 基准保留段，
# 流量实际仍走公网。显式设 LABINFER_ALLOW_FAKEIP=1 才放行这一段，其余拒绝规则不变。
_FAKEIP_NET = ipaddress.ip_network("198.18.0.0/15")
_ALLOW_FAKEIP = os.environ.get("LABINFER_ALLOW_FAKEIP", "").strip().lower() in ("1", "true", "yes")


def validate_outbound_url(url: str) -> None:
    u = urlparse(url)
    if u.scheme != "https":
        raise OutboundError("仅允许 https 出网请求")
    host = u.hostname
    if not host:
        raise OutboundError("URL 缺少主机名")
    if host == "localhost" or host.endswith(".localhost"):
        raise OutboundError(f"拒绝非公网主机 {host}")
    try:
        infos = socket.getaddrinfo(host, u.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise OutboundError(f"主机解析失败: {host}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _ALLOW_FAKEIP and ip in _FAKEIP_NET:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise OutboundError(f"拒绝非公网地址 {host} -> {ip}")


def llm_configured() -> bool:
    return bool(settings.glm_base_url and settings.glm_api_key)


async def chat(messages: list[dict], model: str | None = None, temperature: float = 0.2,
               timeout: float = 60) -> str:
    if not llm_configured():
        raise LlmError("NOT_CONFIGURED", "GLM 未配置（LABINFER_GLM_BASE_URL / LABINFER_GLM_API_KEY）")
    base = settings.glm_base_url.rstrip("/")
    validate_outbound_url(f"{base}/chat/completions")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {settings.glm_api_key}"},
                json={"model": model or settings.llm_model, "messages": messages,
                      "temperature": temperature},
            )
    except httpx.HTTPError as e:
        raise LlmError("NETWORK", f"网络错误: {type(e).__name__}") from e
    if resp.status_code in (401, 403):
        raise LlmError("AUTH", "鉴权失败", resp.status_code)
    if resp.status_code == 404:
        raise LlmError("PATH", "路径不存在，检查 baseUrl", resp.status_code)
    if resp.status_code == 429:
        raise LlmError("RATE_LIMIT", "限流", resp.status_code)
    if resp.status_code != 200:
        raise LlmError("PROVIDER", f"上游返回 {resp.status_code}", resp.status_code)
    try:
        return resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise LlmError("RESPONSE", "响应不兼容") from e
