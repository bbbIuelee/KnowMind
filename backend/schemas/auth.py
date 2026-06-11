"""KnowMind 鉴权接口请求和响应模型。"""

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """用户注册请求模型。"""

    username: str = Field(..., min_length=1, max_length=100, description="用户名")
    password: str = Field(..., min_length=1, description="密码")
    role: str | None = Field(default="user", description="用户角色")
    admin_code: str | None = Field(default=None, description="管理员邀请码")


class LoginRequest(BaseModel):
    """用户登录请求模型。"""

    username: str = Field(..., min_length=1, max_length=100, description="用户名")
    password: str = Field(..., min_length=1, description="密码")


class AuthResponse(BaseModel):
    """注册和登录成功后的令牌响应模型。"""

    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    username: str = Field(..., description="用户名")
    role: str = Field(..., description="用户角色")


class CurrentUserResponse(BaseModel):
    """当前用户信息响应模型。"""

    username: str = Field(..., description="用户名")
    role: str = Field(..., description="用户角色")
