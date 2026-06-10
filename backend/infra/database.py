"""KnowMind 数据库基础设施模块。"""

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from backend.env import load_env


load_env()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/knowmind",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base = declarative_base()


def init_db() -> None:
    """导入 ORM 模型并创建数据库表。"""
    import backend.db.models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db_session() -> Generator[Session, None, None]:
    """提供 FastAPI 依赖使用的数据库会话。"""
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()
