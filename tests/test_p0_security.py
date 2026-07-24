"""P0 安全与数据安全修复的验收测试。

覆盖：
- P0-1 /api/page/ 未登录返回 401
- P0-2 SQLite 撞锁不被误判损坏（不删 WAL / 不 rename）
- P0-3 akshare _run 超时不阻塞、返回空 DataFrame
- P0-4 PBKDF2 哈希 / 旧 SHA-256 无感迁移 / 错误密码 / 改密失效 / 过期 token
- P0-7 skill-chat SSE 静默期发心跳帧
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone

import jwt
import pandas as pd
import pytest
from sqlalchemy import create_engine

from app.akshare_client import AkshareGateway
from app.main import _recover_sqlite_if_corrupted, _skill_chat_stream_generator
from app.models_auth import User
from app.services.auth import AuthService

# 复用 test_api 的带认证 client 装配
from tests.test_api import build_client, build_client_and_gateway


# ── P0-1 ────────────────────────────────────────────────────────────────────

def test_page_endpoint_requires_auth_without_token() -> None:
    """未携带 Bearer token 访问 /api/page/* 应返回 401（P0-1 白名单已移除）。"""
    client, _ = build_client_and_gateway()
    del client.headers["Authorization"]
    resp = client.get("/api/page/home")
    assert resp.status_code == 401


# ── P0-2 ────────────────────────────────────────────────────────────────────

def test_recover_sqlite_locked_not_treated_as_corrupted(tmp_path, monkeypatch) -> None:
    """integrity_check 撞锁只重试，绝不删 WAL / rename DB（连环损坏根因）。"""
    db_path = tmp_path / "test.db"
    db_path.write_bytes(b"sqlite-dummy")
    wal_path = tmp_path / "test.db-wal"
    wal_path.write_bytes(b"WAL-DATA-MUST-SURVIVE")

    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}")

    from sqlalchemy.exc import OperationalError

    def fake_connect():
        raise OperationalError("PRAGMA integrity_check", {}, "database is locked")

    monkeypatch.setattr(engine, "connect", fake_connect)
    monkeypatch.setattr("app.main.time.sleep", lambda *_a, **_kw: None)  # 跳过重试 sleep

    with pytest.raises(RuntimeError, match="拒绝启动"):
        _recover_sqlite_if_corrupted(engine)

    assert db_path.exists(), "DB 文件不应被 rename/删除"
    assert wal_path.exists(), "WAL 文件不应被删除"
    assert wal_path.read_bytes() == b"WAL-DATA-MUST-SURVIVE"
    assert not list(tmp_path.glob("test.db.corrupted.*")), "不应创建 corrupted 备份"


# ── P0-3 ────────────────────────────────────────────────────────────────────

def test_akshare_run_returns_empty_on_timeout_and_does_not_block() -> None:
    """fetcher 卡死时 _run 应在 timeout 内返回空 DataFrame，不阻塞等待线程。"""
    gateway = AkshareGateway()
    release = threading.Event()

    def blocking_fetcher() -> pd.DataFrame:
        release.wait(60)  # 模拟 akshare 内部无 timeout 的挂起
        return pd.DataFrame({"x": [1]})

    start = time.time()
    result = gateway._run(blocking_fetcher, timeout_seconds=2)
    elapsed = time.time() - start
    release.set()  # 释放后台线程

    assert isinstance(result, pd.DataFrame)
    assert result.empty
    assert elapsed < 10, f"_run 阻塞了 {elapsed:.1f}s，未真正做到超时返回"


# ── P0-4 ────────────────────────────────────────────────────────────────────

def test_pbkdf2_hash_and_verify() -> None:
    auth = AuthService(jwt_secret="a" * 40)
    hashed = auth.hash_password("s3cret-pass")
    assert hashed.startswith("pbkdf2$")
    assert auth.verify_password("s3cret-pass", hashed) is True
    assert auth.verify_password("wrong", hashed) is False


def test_legacy_sha256_hash_migrates_on_login(db_session) -> None:
    """旧 SHA-256 哈希在登录验证通过后无感迁移到 PBKDF2。"""
    import hashlib
    import secrets

    auth = AuthService(jwt_secret="b" * 40)
    salt = secrets.token_hex(16)
    legacy_hash = f"{salt}${hashlib.sha256(f'{salt}oldpass'.encode()).hexdigest()}"
    user = User(username="legacy_user", hashed_password=legacy_hash, is_active=True)
    db_session.add(user)
    db_session.commit()

    assert auth.is_legacy_hash(user.hashed_password) is True
    logged_in = auth.authenticate(db_session, "legacy_user", "oldpass")
    assert logged_in is not None

    db_session.refresh(user)
    assert user.hashed_password.startswith("pbkdf2$"), "登录后应迁移到 PBKDF2"
    assert auth.is_legacy_hash(user.hashed_password) is False
    assert auth.verify_password("oldpass", user.hashed_password) is True


def test_login_wrong_password_returns_401() -> None:
    client = build_client()
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_change_password_invalidates_old() -> None:
    client = build_client()
    resp = client.post(
        "/api/auth/change-password",
        json={"old_password": "admin123", "new_password": "new-pass-456"},
    )
    assert resp.status_code == 200

    # 旧密码失效
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 401
    # 新密码可用
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "new-pass-456"})
    assert resp.status_code == 200


def test_expired_token_rejected() -> None:
    from unittest.mock import MagicMock

    auth = AuthService(jwt_secret="c" * 40)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "1",
        "username": "admin",
        "is_admin": True,
        "exp": now - timedelta(hours=1),
        "iat": now - timedelta(hours=2),
    }
    expired = jwt.encode(payload, auth.jwt_secret, algorithm="HS256")
    assert auth.resolve_token(MagicMock(), expired) is None


# ── P0-7 ────────────────────────────────────────────────────────────────────

def test_skill_chat_emits_heartbeat_during_silence(monkeypatch) -> None:
    """Claude 静默期，SSE 生成器应主动发心跳帧（线程+队列驱动，不靠 readline 返回）。"""
    import app.main as main_mod

    monkeypatch.setattr(main_mod, "_SKILL_CHAT_HEARTBEAT_SECONDS", 1)
    monkeypatch.setattr(main_mod, "_SKILL_CHAT_TIMEOUT_SECONDS", 30)

    release = threading.Event()

    class FakeStdout:
        def readline(self):
            release.wait(30)  # 静默：readline 长时间不返回
            return ""  # EOF

    class FakeProc:
        returncode = 0
        stdout = FakeStdout()

        class _Err:
            def read(self):
                return ""

        stderr = _Err()

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

        def kill(self):
            release.set()

    monkeypatch.setattr(main_mod.subprocess, "Popen", lambda *a, **k: FakeProc())

    events: list[bytes] = []
    gen = _skill_chat_stream_generator("/fake/claude", "prompt")
    try:
        for ev in gen:
            if isinstance(ev, (bytes, bytearray)):
                events.append(bytes(ev))
            if any(b": ping" in e for e in events):
                break  # 收到心跳即足够
    finally:
        release.set()  # 解除 readline 阻塞，让生成器收尾

    assert any(b": ping" in e for e in events), "静默期应发心跳帧"
