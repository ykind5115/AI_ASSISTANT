"""
API 依赖项
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.models.schema import get_db, User
from app.services.auth_service import AuthService


def get_current_user_optional(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
) -> Optional[User]:
    return AuthService(db).get_user_from_authorization(authorization)


def get_current_user(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
) -> User:
    user = AuthService(db).get_user_from_authorization(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return user

