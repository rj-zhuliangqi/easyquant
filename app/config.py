import logging
import os
import secrets
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DEFAULT_DATABASE_URL = f"sqlite+pysqlite:///{(DATA_DIR / 'sector_fund_monitor.db').as_posix()}"
AI_CENTER_DIR = DATA_DIR / "ai_center"
AI_CENTER_INBOX_DIR = AI_CENTER_DIR / "inbox"
AI_CENTER_PROCESSED_DIR = AI_CENTER_DIR / "processed"
AI_CENTER_DIR.mkdir(exist_ok=True)
AI_CENTER_INBOX_DIR.mkdir(exist_ok=True)
AI_CENTER_PROCESSED_DIR.mkdir(exist_ok=True)

# Auth configuration
_JWT_SECRET_FILE = DATA_DIR / ".jwt_secret"


def _load_or_create_jwt_secret() -> str:
    """加载或生成 JWT 密钥，杜绝使用默认弱密钥。

    优先级：EQ_JWT_SECRET 环境变量 > data/.jwt_secret 持久化文件 > 现场生成并写回文件。
    生成的密钥为 48 字节随机串（token_urlsafe），满足 >=32 字节要求。
    """
    env_secret = os.environ.get("EQ_JWT_SECRET")
    if env_secret:
        if len(env_secret) < 32:
            logger.warning("EQ_JWT_SECRET 长度 %d < 32，建议使用更长的密钥", len(env_secret))
        return env_secret
    try:
        if _JWT_SECRET_FILE.exists():
            stored = _JWT_SECRET_FILE.read_text(encoding="utf-8").strip()
            if stored:
                return stored
    except OSError:
        logger.warning("读取 JWT 密钥文件失败，将生成新密钥", exc_info=True)
    new_secret = secrets.token_urlsafe(48)
    try:
        _JWT_SECRET_FILE.write_text(new_secret, encoding="utf-8")
        try:
            os.chmod(_JWT_SECRET_FILE, 0o600)
        except OSError:
            pass
        logger.warning("已生成随机 JWT 密钥并持久化到 %s", _JWT_SECRET_FILE)
    except OSError as exc:
        logger.error(
            "无法写入 JWT 密钥文件 %s: %s - 使用进程内随机密钥（重启后所有 token 失效）",
            _JWT_SECRET_FILE, exc,
        )
    return new_secret


JWT_SECRET = _load_or_create_jwt_secret()
JWT_EXPIRE_HOURS = int(os.environ.get("EQ_JWT_EXPIRE_HOURS", "168"))  # 7 days
