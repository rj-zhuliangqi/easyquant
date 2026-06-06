from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class AuthMiddleware(BaseHTTPMiddleware):
    """Protect all /api/ endpoints except /api/auth/ with JWT authentication."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Only protect /api/ paths, exclude auth and health endpoints
        public_paths = ("/api/auth/", "/api/status", "/api/page/")
        if path.startswith("/api/") and not any(path.startswith(p) for p in public_paths):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse(status_code=401, content={"detail": "未提供认证凭证"})
            token = auth_header[7:]
            auth_service = request.app.state.auth_service
            # Get a db session for token resolution
            session_factory = request.app.state.session_factory
            with session_factory() as session:
                user = auth_service.resolve_token(session, token)
            if user is None:
                return JSONResponse(status_code=401, content={"detail": "登录已过期，请重新登录"})
            request.state.user = user
        return await call_next(request)
