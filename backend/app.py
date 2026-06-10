"""KnowMind FastAPI 应用创建模块。"""

import os
import sys
from pathlib import Path


# 支持 `python backend/app.py` 与 `uvicorn backend.app:app` 两种启动方式。
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.router import router
from backend.env import PROJECT_ROOT, load_env
from backend.infra.database import init_db


load_env()


def create_app() -> FastAPI:
    """创建并配置 KnowMind FastAPI 应用实例。"""
    app = FastAPI(title="KnowMind API", version="0.1.0")

    @app.on_event("startup")
    async def startup_init_db() -> None:
        """应用启动时初始化数据库表。"""
        init_db()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    app.mount("/", StaticFiles(directory=PROJECT_ROOT / "frontend", html=True), name="frontend")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )
