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

from backend.api.router import router
from backend.env import load_env


load_env()


def create_app() -> FastAPI:
    """创建并配置 KnowMind FastAPI 应用实例。"""
    app = FastAPI(title="KnowMind API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )
