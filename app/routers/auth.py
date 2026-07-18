from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

security = HTTPBearer(auto_error=False)


# --- Schemas ---

class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    is_admin: bool = False


class ResetPasswordRequest(BaseModel):
    new_password: str


class ToggleActiveRequest(BaseModel):
    pass  # no body needed, just the user id in URL


# --- Current user (detached from session) ---

@dataclass
class CurrentUser:
    id: int
    username: str
    hashed_password: str
    is_active: bool
    is_admin: bool

    @classmethod
    def from_orm(cls, user: User) -> "CurrentUser":
        return cls(id=user.id, username=user.username, hashed_password=user.hashed_password,
                   is_active=user.is_active, is_admin=user.is_admin)


# --- Helpers ---

def _get_auth_service(request: Request):
    return request.app.state.auth_service


def _get_db(request: Request):
    return request.app.state.get_db()


def _require_admin(current_user: CurrentUser) -> CurrentUser:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    request: Request = None,
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status_code=401, detail="未提供认证凭证")
    auth = _get_auth_service(request)
    get_db = _get_db(request)
    db = next(get_db)
    try:
        user = auth.resolve_token(db, credentials.credentials)
        if user is None:
            raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
        return CurrentUser.from_orm(user)
    finally:
        db.close()


# --- Public endpoints ---

@router.post("/login")
def login(body: LoginRequest, request: Request) -> dict:
    auth = _get_auth_service(request)
    get_db = _get_db(request)
    db = next(get_db)
    try:
        user = auth.authenticate(db, body.username, body.password)
        if user is None:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        user_id, username, is_admin = user.id, user.username, user.is_admin
    finally:
        db.close()
    token = auth.create_token_for(user_id, username, is_admin)
    return {"access_token": token, "token_type": "bearer", "username": username, "is_admin": is_admin}


# --- Authenticated endpoints ---

@router.get("/me")
def me(current_user: CurrentUser = Depends(get_current_user)) -> dict:
    return {"id": current_user.id, "username": current_user.username,
            "is_active": current_user.is_active, "is_admin": current_user.is_admin}


@router.post("/change-password")
def change_password(body: ChangePasswordRequest, current_user: CurrentUser = Depends(get_current_user), request: Request = None) -> dict:
    auth = _get_auth_service(request)
    get_db = _get_db(request)
    db = next(get_db)
    try:
        user = db.get(User, current_user.id)
        if user is None:
            raise HTTPException(status_code=401, detail="用户不存在")
        if not auth.change_password(db, user, body.old_password, body.new_password):
            raise HTTPException(status_code=400, detail="旧密码错误")
    finally:
        db.close()
    return {"message": "密码修改成功"}


# --- Admin endpoints ---

@router.get("/users")
def list_users(current_user: CurrentUser = Depends(get_current_user), request: Request = None) -> dict:
    _require_admin(current_user)
    auth = _get_auth_service(request)
    get_db = _get_db(request)
    db = next(get_db)
    try:
        users = auth.list_users(db)
        return {"users": [
            {"id": u.id, "username": u.username, "is_active": u.is_active,
             "is_admin": u.is_admin, "created_at": u.created_at.isoformat() if u.created_at else None,
             "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None}
            for u in users
        ]}
    finally:
        db.close()


@router.post("/users")
def create_user(body: CreateUserRequest, current_user: CurrentUser = Depends(get_current_user), request: Request = None) -> dict:
    _require_admin(current_user)
    auth = _get_auth_service(request)
    get_db = _get_db(request)
    db = next(get_db)
    try:
        user = auth.create_user(db, body.username, body.password, is_admin=body.is_admin)
        return {"id": user.id, "username": user.username, "is_admin": user.is_admin}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        db.close()


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, body: ResetPasswordRequest, current_user: CurrentUser = Depends(get_current_user), request: Request = None) -> dict:
    _require_admin(current_user)
    auth = _get_auth_service(request)
    get_db = _get_db(request)
    db = next(get_db)
    try:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        auth.reset_password(db, user, body.new_password)
        return {"message": "密码已重置"}
    finally:
        db.close()


@router.post("/users/{user_id}/toggle-active")
def toggle_active(user_id: int, current_user: CurrentUser = Depends(get_current_user), request: Request = None) -> dict:
    _require_admin(current_user)
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能禁用自己")
    auth = _get_auth_service(request)
    get_db = _get_db(request)
    db = next(get_db)
    try:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        auth.toggle_user_active(db, user)
        return {"id": user.id, "username": user.username, "is_active": user.is_active}
    finally:
        db.close()


@router.delete("/users/{user_id}")
def delete_user(user_id: int, current_user: CurrentUser = Depends(get_current_user), request: Request = None) -> dict:
    _require_admin(current_user)
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    auth = _get_auth_service(request)
    get_db = _get_db(request)
    db = next(get_db)
    try:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        auth.delete_user(db, user)
        return {"message": f"用户 {user.username} 已删除"}
    finally:
        db.close()
