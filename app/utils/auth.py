"""
认证工具
提供密码哈希与 Token 处理（不依赖第三方库）
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from typing import Optional


_PBKDF2_ALG = "pbkdf2_sha256"
_PBKDF2_HASH_NAME = "sha256"
_PBKDF2_ITERATIONS = 200_000
_SALT_BYTES = 16
_HASH_BYTES = 32


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64d(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str) -> str:
    """生成密码哈希：pbkdf2_sha256$iters$salt$hash"""
    salt = os.urandom(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        _PBKDF2_HASH_NAME,
        password.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
        dklen=_HASH_BYTES,
    )
    return f"{_PBKDF2_ALG}${_PBKDF2_ITERATIONS}${_b64e(salt)}${_b64e(derived)}"


def verify_password(password: str, stored_hash: str) -> bool:
    """校验密码哈希"""
    try:
        alg, iters_str, salt_b64, derived_b64 = stored_hash.split("$", 3)
        if alg != _PBKDF2_ALG:
            return False
        iters = int(iters_str)
        salt = _b64d(salt_b64)
        expected = _b64d(derived_b64)
    except Exception:
        return False

    computed = hashlib.pbkdf2_hmac(
        _PBKDF2_HASH_NAME,
        password.encode("utf-8"),
        salt,
        iters,
        dklen=len(expected),
    )
    return hmac.compare_digest(computed, expected)


def generate_token(nbytes: int) -> str:
    """生成随机 Token（明文返回给客户端）"""
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """对 Token 进行不可逆哈希后保存到数据库"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    """从 Authorization: Bearer <token> 提取 token"""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2:
        return None
    if parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None

