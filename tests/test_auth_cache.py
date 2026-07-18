"""AuthMiddleware token->user LRU 缓存测试（C4）。"""
from __future__ import annotations

import time

from app.dependencies import _TokenUserCache


def test_token_cache_hits_within_ttl() -> None:
    """30s TTL 内同 token 复用，不重复查库。"""
    cache = _TokenUserCache(ttl=30.0, maxsize=256)
    cache.set("tok-A", {"id": 1, "username": "admin"})
    assert cache.get("tok-A") == {"id": 1, "username": "admin"}
    assert cache.get("tok-A") == {"id": 1, "username": "admin"}  # 复用


def test_token_cache_expires_after_ttl() -> None:
    """TTL 过期后 get 返回 None（穿透重查）。"""
    cache = _TokenUserCache(ttl=0, maxsize=256)  # 立即过期
    cache.set("tok-A", {"id": 1})
    assert cache.get("tok-A") is None


def test_token_cache_lru_eviction() -> None:
    """超过 maxsize 淘汰最久未用。"""
    cache = _TokenUserCache(ttl=30.0, maxsize=2)
    cache.set("tok-A", {"id": 1})
    cache.set("tok-B", {"id": 2})
    cache.get("tok-A")  # A 近期访问 -> B 成最久未用
    cache.set("tok-C", {"id": 3})  # 超 maxsize，淘汰 B
    assert cache.get("tok-A") == {"id": 1}
    assert cache.get("tok-C") == {"id": 3}
    assert cache.get("tok-B") is None  # 被淘汰


def test_token_cache_does_not_cache_none() -> None:
    """失效 token 不缓存（set 仅在 user 非 None 时调用，这里验证语义）。"""
    cache = _TokenUserCache(ttl=30.0, maxsize=256)
    # 模拟 resolve 返回 None -> 不 set -> 后续 get 永远 miss
    assert cache.get("invalid-tok") is None
    assert cache.get("invalid-tok") is None


def test_token_cache_invalidate() -> None:
    """invalidate 单 token 或全清。"""
    cache = _TokenUserCache(ttl=30.0, maxsize=256)
    cache.set("tok-A", {"id": 1})
    cache.set("tok-B", {"id": 2})
    cache.invalidate("tok-A")
    assert cache.get("tok-A") is None
    assert cache.get("tok-B") == {"id": 2}
    cache.invalidate()  # 全清
    assert cache.get("tok-B") is None


def test_middleware_caches_repeated_token(monkeypatch) -> None:
    """端到端：连续同 token 请求，resolve_token 只被调 1 次。"""
    import app.dependencies as deps
    from tests.test_api import build_client

    # 计数 resolve_token 调用
    call_count = {"n": 0}
    real_resolve = deps._resolve_user_from_token

    def counting_resolve(session_factory, auth_service, token):
        call_count["n"] += 1
        return real_resolve(session_factory, auth_service, token)

    monkeypatch.setattr(deps, "_resolve_user_from_token", counting_resolve)
    # 用独立缓存避免与其他测试串
    fresh = deps._TokenUserCache(ttl=30.0, maxsize=256)
    monkeypatch.setattr(deps, "_TOKEN_CACHE", fresh)

    client = build_client()
    # 登录拿 token
    # build_client 已 attach admin auth（_attach_admin_auth），直接取其 headers
    auth = getattr(client, "headers", {})
    token = auth.get("Authorization", "").replace("Bearer ", "")
    assert token, "build_client 应已附加 admin token"

    # 连续 3 次打受保护接口
    for _ in range(3):
        r = client.get("/api/page/workspace")
        assert r.status_code == 200, r.text

    # 首次 miss 查 1 次，后续 2 次命中缓存 -> 总共 1 次
    assert call_count["n"] == 1, f"30s 内应只查 1 次 users 表，实际 {call_count['n']}"
