from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any

from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class _TokenUserCache:
    """C4: token -> user 进程内 LRU + TTL 缓存。

    每个受保护请求原本都要开 session 查 users 表；JWT 已含 user_id/username/
    is_admin，DB 查询仅为确认用户仍存在且 is_active。30s 内同 token 复用结果，
    高并发下显著减负。仅缓存成功解析（user 非 None）；失效/过期 token 不缓存，
    避免持有 stale 否定结果。
    """

    def __init__(self, ttl: float = 30.0, maxsize: int = 256) -> None:
        self.ttl = ttl
        self.maxsize = maxsize
        self._store: "OrderedDict[str, tuple[Any, float]]" = OrderedDict()

    def get(self, token: str) -> Any | None:
        entry = self._store.get(token)
        if entry is None:
            return None
        user, expires_at = entry
        if time.time() >= expires_at:
            self._store.pop(token, None)
            return None
        self._store.move_to_end(token)  # LRU 近期访问置尾
        return user

    def set(self, token: str, user: Any) -> None:
        self._store[token] = (user, time.time() + self.ttl)
        self._store.move_to_end(token)
        while len(self._store) > self.maxsize:
            self._store.popitem(last=False)  # 淘汰最久未用

    def invalidate(self, token: str | None = None) -> None:
        if token is None:
            self._store.clear()
        else:
            self._store.pop(token, None)


# 进程级单例；测试可通过替换 _TOKEN_CACHE 注入
_TOKEN_CACHE = _TokenUserCache()


def _resolve_user_from_token(session_factory, auth_service, token):
    """同步 SQLite 查询放到线程池执行，避免阻塞事件循环。"""
    with session_factory() as session:
        return auth_service.resolve_token(session, token)


class AuthMiddleware(BaseHTTPMiddleware):
    """Protect all /api/ endpoints except /api/auth/ and /api/status with JWT.

    注意：``/api/page/`` 不再放行 -- 页面聚合接口同样需要登录态。
    token 校验通过 ``run_in_threadpool`` 在线程池中查库，避免 SQLite 写锁
    占用时 ``busy_timeout`` 冻结事件循环最长 30s。

    C4: 30s LRU 缓存（``_TOKEN_CACHE``）让同 token 连续请求只查 1 次 users 表。
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        public_paths = ("/api/auth/", "/api/status")
        if path.startswith("/api/") and not any(path.startswith(p) for p in public_paths):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse(status_code=401, content={"detail": "未提供认证凭证"})
            token = auth_header[7:]
            user = _TOKEN_CACHE.get(token)
            if user is None:
                auth_service = request.app.state.auth_service
                session_factory = request.app.state.session_factory
                user = await run_in_threadpool(
                    _resolve_user_from_token, session_factory, auth_service, token
                )
                if user is not None:
                    _TOKEN_CACHE.set(token, user)
            if user is None:
                return JSONResponse(status_code=401, content={"detail": "登录已过期，请重新登录"})
            request.state.user = user
        return await call_next(request)
