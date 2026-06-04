"""KnowMind 项目启动入口。"""

import os

import uvicorn

from backend.app import app


def main() -> None:
    """按环境变量配置启动 KnowMind FastAPI 服务。"""
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )


if __name__ == "__main__":
    main()
