"""KnowMind 后端 API 路由聚合模块。"""

from fastapi import APIRouter


router = APIRouter()


@router.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """返回 KnowMind 服务健康检查信息。"""
    return {"status": "ok", "service": "knowmind"}
