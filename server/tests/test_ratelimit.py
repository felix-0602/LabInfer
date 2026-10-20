import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app
from app.ratelimit import MODEL_LIMIT, RateLimitMiddleware
from app.storage import Store


def make_bare_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.post("/api/m1/ping")
    def m1_ping():
        return {"ok": True}

    @app.post("/api/other")
    def other():
        return {"ok": True}

    @app.get("/api/m1/get")
    def get():
        return {"ok": True}

    return TestClient(app)


def test_model_post_over_limit_gets_429():
    c = make_bare_client()
    for _ in range(MODEL_LIMIT):
        assert c.post("/api/m1/ping").status_code == 200
    r = c.post("/api/m1/ping")
    assert r.status_code == 429
    assert r.json()["detail"].startswith("rate limit")
    assert "retry-after" in r.headers


def test_general_bucket_and_get_not_limited():
    c = make_bare_client()
    for _ in range(MODEL_LIMIT + 5):
        assert c.post("/api/other").status_code == 200
    for _ in range(MODEL_LIMIT + 30):
        assert c.get("/api/m1/get").status_code == 200


def test_web_dist_mount(tmp_path):
    (tmp_path / "index.html").write_text("<html>labinfer</html>", encoding="utf-8")
    os.environ["LABINFER_WEB_DIST"] = str(tmp_path)
    try:
        client = TestClient(create_app(Store(tmp_path / "data")))
        assert "labinfer" in client.get("/").text
        assert client.get("/api/health").status_code == 200  # /api 路由优先于静态兜底
    finally:
        del os.environ["LABINFER_WEB_DIST"]
