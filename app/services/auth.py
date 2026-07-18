from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy.orm import Session

from app.config import JWT_EXPIRE_HOURS, JWT_SECRET
from app.models_auth import User

logger = logging.getLogger(__name__)

# PBKDF2 迭代次数（OWASP 2023 推荐 sha256 下 600k 次）
_PBKDF2_ITERATIONS = 600_000


class AuthService:
    def __init__(self, *, jwt_secret: str = JWT_SECRET, jwt_expire_hours: int = JWT_EXPIRE_HOURS) -> None:
        self.jwt_secret = jwt_secret
        self.jwt_expire_hours = jwt_expire_hours

    # -- password hashing (PBKDF2-HMAC-SHA256, stdlib only) --

    @staticmethod
    def hash_password(password: str) -> str:
        """用 PBKDF2-HMAC-SHA256 + 随机 salt 哈希密码。

        存储格式: ``pbkdf2$<iterations>$<salt_hex>$<hash_hex>``
        """
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
        return f"pbkdf2${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"

    @staticmethod
    def is_legacy_hash(hashed: str) -> bool:
        """旧 SHA-256 格式（``salt$digest``）需迁移到 PBKDF2。"""
        return not hashed.startswith("pbkdf2$")

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """校验密码（恒定时间比较），兼容旧 SHA-256 格式。"""
        if hashed.startswith("pbkdf2$"):
            try:
                _, iter_str, salt_hex, hash_hex = hashed.split("$")
                iterations = int(iter_str)
                salt = bytes.fromhex(salt_hex)
                expected = bytes.fromhex(hash_hex)
            except (ValueError, IndexError):
                return False
            actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
            return hmac.compare_digest(actual, expected)
        # legacy SHA-256: salt$digest
        try:
            salt, digest = hashed.split("$", 1)
        except ValueError:
            return False
        actual = hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()
        return hmac.compare_digest(actual, digest)

    # -- JWT --

    def create_token_for(self, user_id: int, username: str, is_admin: bool = False) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "username": username,
            "is_admin": is_admin,
            "exp": now + timedelta(hours=self.jwt_expire_hours),
            "iat": now,
        }
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    def resolve_token(self, session: Session, token: str) -> User | None:
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None
        user_id = payload.get("sub")
        if user_id is None:
            return None
        user = session.get(User, int(user_id))
        if user is None or not user.is_active:
            return None
        return user

    # -- user management --

    def authenticate(self, session: Session, username: str, password: str) -> User | None:
        user = session.query(User).filter(User.username == username).first()
        if user is None or not user.is_active:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        # 旧 SHA-256 哈希无感迁移到 PBKDF2
        if self.is_legacy_hash(user.hashed_password):
            user.hashed_password = self.hash_password(password)
            session.commit()
        user.last_login_at = datetime.now()
        session.commit()
        return user

    def create_user(self, session: Session, username: str, password: str, is_admin: bool = False) -> User:
        existing = session.query(User).filter(User.username == username).first()
        if existing is not None:
            raise ValueError(f"用户名 '{username}' 已存在")
        user = User(
            username=username,
            hashed_password=self.hash_password(password),
            is_admin=is_admin,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        logger.info("created user: %s (admin=%s)", username, is_admin)
        return user

    def change_password(self, session: Session, user: User, old_password: str, new_password: str) -> bool:
        if not self.verify_password(old_password, user.hashed_password):
            return False
        user.hashed_password = self.hash_password(new_password)
        session.commit()
        return True

    def reset_password(self, session: Session, user: User, new_password: str) -> None:
        user.hashed_password = self.hash_password(new_password)
        session.commit()
        logger.info("password reset for user: %s", user.username)

    def toggle_user_active(self, session: Session, user: User) -> None:
        user.is_active = not user.is_active
        session.commit()

    def delete_user(self, session: Session, user: User) -> None:
        session.delete(user)
        session.commit()
        logger.info("deleted user: %s", user.username)

    def list_users(self, session: Session) -> list[User]:
        return session.query(User).order_by(User.id).all()

    def ensure_default_admin(self, session: Session) -> None:
        """无用户时创建默认管理员，使用随机初始密码并打印到启动日志。"""
        user_count = session.query(User).count()
        if user_count == 0:
            password = secrets.token_urlsafe(12)
            self.create_user(session, "admin", password, is_admin=True)
            logger.warning("=" * 64)
            logger.warning("已创建默认管理员 admin，初始密码：%s", password)
            logger.warning("请立即登录并在「用户管理」页修改密码。")
            logger.warning("=" * 64)
