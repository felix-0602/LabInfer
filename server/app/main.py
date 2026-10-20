import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import CONTRACT_VERSION
from .routers import contexts, datasets, m1, m2, m4, m5, m6, m7, snapshot
from .ratelimit import RateLimitMiddleware
from .storage import Store, store_from_env


def create_app(store: Store | None = None) -> FastAPI:
    app = FastAPI(title="LabInfer API", version=CONTRACT_VERSION)
    app.state.store = store or store_from_env()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health():
        return {"status": "ok", "contract_version": CONTRACT_VERSION}

    for r in (datasets.router, contexts.router, m1.router, m2.router, m4.router,
              m5.router, m6.router, m7.router, snapshot.router):
        app.include_router(r)

    # 公网部署防护（DEPLOY.md 第 4 节）：LABINFER_RATELIMIT=0 关闭（本地测试用）
    if os.environ.get("LABINFER_RATELIMIT", "1") != "0":
        app.add_middleware(RateLimitMiddleware)

    # 单端口形态：设 LABINFER_WEB_DIST 指向前端构建产物，FastAPI 直接伺服
    # （挂在所有 /api 路由之后，静态兜底；前端只用相对路径 /api，无需跨域）
    web_dist = os.environ.get("LABINFER_WEB_DIST", "")
    if web_dist and Path(web_dist).is_dir():
        app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
    return app


app = create_app()
