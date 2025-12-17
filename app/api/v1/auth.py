"""
认证 API
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.models.schema import get_db, User
from app.services.auth_service import AuthService
from app.utils.auth import extract_bearer_token

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: Optional[str] = None


class RegisterResponse(BaseModel):
    user_id: int
    username: str
    display_name: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    display_name: str


class MeResponse(BaseModel):
    user_id: int
    display_name: str


@router.post("/auth/register", response_model=RegisterResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    try:
        user = service.register(request.username, request.password, request.display_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return RegisterResponse(
        user_id=user.id,
        username=request.username.strip(),
        display_name=user.display_name,
    )


@router.post("/auth/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    user = service.authenticate(request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = service.issue_token(user)
    return LoginResponse(
        access_token=token,
        user_id=user.id,
        username=request.username.strip(),
        display_name=user.display_name,
    )


@router.get("/auth/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user)):
    return MeResponse(user_id=current_user.id, display_name=current_user.display_name)


@router.post("/auth/logout")
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
):
    token = extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=400, detail="缺少 Authorization: Bearer <token>")

    service = AuthService(db)
    service.revoke_token(token)
    return {"message": "已退出登录"}

