from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy.orm import Session

from app.config import JWT_EXPIRE_HOURS, JWT_SECRET
from app.models_auth import User

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, *, jwt_secret: str = JWT_SECRET, jwt_expire_hours: int = JWT_EXPIRE_HOURS) -> None:
        self.jwt_secret = jwt_secret
        self.jwt_expire_hours = jwt_expire_hours

    # -- password hashing (lightweight, no external deps) --

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password with a random salt using SHA-256."""
        import secrets
        salt = secrets.token_hex(16)
        digest = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return f"{salt}${digest}"

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify a password against its hash."""
        try:
            salt, digest = hashed.split("$", 1)
        except ValueError:
            return False
        return hashlib.sha256(f"{salt}{password}".encode()).hexdigest() == digest

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
        """Create a default admin user if no users exist."""
        user_count = session.query(User).count()
        if user_count == 0:
            self.create_user(session, "admin", "admin123", is_admin=True)
            logger.warning("created default admin user (admin/admin123) — please change the password!")
