"""KnowMind 用户注册、登录和当前用户接口。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.models import User
from backend.infra.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    get_password_hash,
    resolve_role,
)
from backend.infra.database import get_db_session
from backend.schemas.auth import AuthResponse, CurrentUserResponse, LoginRequest, RegisterRequest


router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=AuthResponse)
def register(request: RegisterRequest, db_session: Session = Depends(get_db_session)) -> AuthResponse:
    """注册普通用户或管理员用户，并返回访问令牌。"""
    username = request.username.strip()
    password = request.password.strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")

    exists = db_session.query(User).filter(User.username == username).first()
    if exists:
        raise HTTPException(status_code=409, detail="用户名已存在")

    role = resolve_role(request.role, request.admin_code)
    user = User(username=username, password_hash=get_password_hash(password), role=role)
    db_session.add(user)
    db_session.commit()

    token = create_access_token(username=username, role=role)
    return AuthResponse(access_token=token, username=username, role=role)


@router.post("/auth/login", response_model=AuthResponse)
def login(request: LoginRequest, db_session: Session = Depends(get_db_session)) -> AuthResponse:
    """校验用户名和密码，并返回访问令牌。"""
    username = request.username.strip()
    password = request.password.strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")

    user = authenticate_user(db_session, username, password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token(username=user.username, role=user.role)
    return AuthResponse(access_token=token, username=user.username, role=user.role)


@router.get("/auth/me", response_model=CurrentUserResponse)
def me(current_user: User = Depends(get_current_user)) -> CurrentUserResponse:
    """返回当前 Bearer Token 对应的用户信息。"""
    return CurrentUserResponse(username=current_user.username, role=current_user.role)
