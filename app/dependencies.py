from __future__ import annotations

from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


def _resolve_user_from_token(session_factory, auth_service, token):
    """同步 SQLite 查询放到线程池执行，避免阻塞事件循环。"""
    with session_factory() as session:
        return auth_service.resolve_token(session, token)


class AuthMiddleware(BaseHTTPMiddleware):
    """Protect all /api/ endpoints except /api/auth/ and /api/status with JWT.

    注意：``/api/page/`` 不再放行 -- 页面聚合接口同样需要登录态。
    token 校验通过 ``run_in_threadpool`` 在线程池中查库，避免 SQLite 写锁
    占用时 ``busy_timeout`` 冻结事件循环最长 30s。
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        public_paths = ("/api/auth/", "/api/status")
        if path.startswith("/api/") and not any(path.startswith(p) for p in public_paths):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse(status_code=401, content={"detail": "未提供认证凭证"})
            token = auth_header[7:]
            auth_service = request.app.state.auth_service
            session_factory = request.app.state.session_factory
            user = await run_in_threadpool(
                _resolve_user_from_token, session_factory, auth_service, token
            )
            if user is None:
                return JSONResponse(status_code=401, content={"detail": "登录已过期，请重新登录"})
            request.state.user = user
        return await call_next(request)
