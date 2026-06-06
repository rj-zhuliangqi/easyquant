from pathlib import Path
import os


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
JWT_SECRET = os.environ.get("EQ_JWT_SECRET", "change-me-in-production")
JWT_EXPIRE_HOURS = int(os.environ.get("EQ_JWT_EXPIRE_HOURS", "168"))  # 7 days
