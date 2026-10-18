from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import CONTRACT_VERSION
from .routers import contexts, datasets, m1, m4, m5, m6, m7, snapshot
from .storage import Store


def create_app(store: Store | None = None) -> FastAPI:
    app = FastAPI(title="LabInfer API", version=CONTRACT_VERSION)
    app.state.store = store or Store()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health():
        return {"status": "ok", "contract_version": CONTRACT_VERSION}

    for r in (datasets.router, contexts.router, m1.router, m4.router,
              m5.router, m6.router, m7.router, snapshot.router):
        app.include_router(r)
    return app


app = create_app()
