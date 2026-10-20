"""按 IP 的滑动窗口限速（防公网扫描烧 GLM 余额，见 DEPLOY.md 第 4 节）。

无新依赖的纯 ASGI 中间件，进程内存计数（部署为单 worker）。
- m1/m2/m5 的 POST（会出网调模型）：MODEL_LIMIT 次/分/IP
- 其余 /api 的 POST（本地写盘）：GENERAL_LIMIT 次/分/IP
GET 不限（健康检查、图片读取、演示页面加载都不受影响）。
"""

import time
from collections import defaultdict, deque

MODEL_PREFIXES = ("/api/m1", "/api/m2", "/api/m5")
MODEL_LIMIT = 10  # 次/分/IP
GENERAL_LIMIT = 60
WINDOW_SECONDS = 60.0


class RateLimitMiddleware:
    def __init__(self, app):
        self.app = app
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _probe(self, key: str, limit: int, now: float) -> int:
        """未超限记一次并返回 0；超限返回建议重试秒数。"""
        q = self._hits[key]
        while q and q[0] <= now - WINDOW_SECONDS:
            q.popleft()
        if len(q) >= limit:
            return max(1, int(WINDOW_SECONDS - (now - q[0])) + 1)
        q.append(now)
        # 公网扫描器会换着 IP 打，防止计数表无限增长
        if len(self._hits) > 4096:
            for k in [k for k, v in self._hits.items() if not v or v[-1] <= now - WINDOW_SECONDS]:
                del self._hits[k]
        return 0

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("method") == "POST" \
                and scope.get("path", "").startswith("/api"):
            ip = (scope.get("client") or ("unknown", 0))[0]
            now = time.monotonic()
            path = scope["path"]
            if any(path.startswith(p) for p in MODEL_PREFIXES):
                retry_after = self._probe(f"m:{ip}", MODEL_LIMIT, now)
            else:
                retry_after = self._probe(f"g:{ip}", GENERAL_LIMIT, now)
            if retry_after:
                body = b'{"detail": "rate limit exceeded, retry later"}'
                await send({"type": "http.response.start", "status": 429,
                            "headers": [(b"content-type", b"application/json"),
                                        (b"retry-after", str(retry_after).encode())]})
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)
