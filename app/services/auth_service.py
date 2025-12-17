"""
认证服务
负责用户注册/登录与 Token 会话管理
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.models.schema import User, UserCredential, AuthToken
from app.utils.auth import (
    extract_bearer_token,
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)


class AuthService:
    """认证服务"""

    def __init__(self, db: Session):
        self.db = db

    def register(self, username: str, password: str, display_name: Optional[str] = None) -> User:
        """注册用户并保存凭据"""
        username = (username or "").strip()
        if len(username) < 3 or len(username) > 64:
            raise ValueError("用户名长度需在 3-64 之间")
        if len(password or "") < 6:
            raise ValueError("密码长度至少 6 位")

        existing = self.db.query(UserCredential).filter(UserCredential.username == username).first()
        if existing:
            raise ValueError("用户名已存在")

        user = User(display_name=display_name or username, preferences={})
        credential = UserCredential(
            username=username,
            password_hash=hash_password(password),
            created_at=datetime.utcnow(),
        )

        try:
            self.db.add(user)
            self.db.flush()  # 获取 user.id
            credential.user_id = user.id
            self.db.add(credential)
            self.db.commit()
            self.db.refresh(user)
            return user
        except Exception:
            self.db.rollback()
            raise

    def authenticate(self, username: str, password: str) -> Optional[User]:
        """校验用户名密码，返回用户"""
        username = (username or "").strip()
        credential = self.db.query(UserCredential).filter(UserCredential.username == username).first()
        if not credential:
            return None
        if not verify_password(password or "", credential.password_hash):
            return None

        user = self.db.query(User).filter(User.id == credential.user_id).first()
        if not user:
            return None

        credential.last_login_at = datetime.utcnow()
        self.db.commit()
        return user

    def issue_token(self, user: User) -> str:
        """签发 Token（明文返回给客户端，哈希存库）"""
        token = generate_token(settings.AUTH_TOKEN_BYTES)
        token_hash_value = hash_token(token)
        now = datetime.utcnow()
        expires_at = now + timedelta(days=settings.AUTH_TOKEN_EXPIRE_DAYS)

        db_token = AuthToken(
            user_id=user.id,
            token_hash=token_hash_value,
            created_at=now,
            expires_at=expires_at,
            last_used_at=now,
            revoked_at=None,
        )
        self.db.add(db_token)
        self.db.commit()
        return token

    def get_user_by_token(self, token: str) -> Optional[User]:
        """通过 Token 获取用户（无效/过期/注销返回 None）"""
        token = (token or "").strip()
        if not token:
            return None

        token_hash_value = hash_token(token)
        now = datetime.utcnow()
        db_token = (
            self.db.query(AuthToken)
            .filter(
                AuthToken.token_hash == token_hash_value,
                AuthToken.revoked_at.is_(None),
                AuthToken.expires_at > now,
            )
            .first()
        )
        if not db_token:
            return None

        db_token.last_used_at = now
        self.db.commit()

        return self.db.query(User).filter(User.id == db_token.user_id).first()

    def revoke_token(self, token: str) -> bool:
        """注销 Token"""
        token_hash_value = hash_token((token or "").strip())
        db_token = self.db.query(AuthToken).filter(AuthToken.token_hash == token_hash_value).first()
        if not db_token:
            return False
        db_token.revoked_at = datetime.utcnow()
        self.db.commit()
        return True

    def get_user_from_authorization(self, authorization: Optional[str]) -> Optional[User]:
        """从 Authorization Header 中解析并获取用户（可选）"""
        token = extract_bearer_token(authorization)
        if not token:
            return None
        return self.get_user_by_token(token)

