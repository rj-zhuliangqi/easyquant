from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DEFAULT_DATABASE_URL = f"sqlite+pysqlite:///{(DATA_DIR / 'sector_fund_monitor.db').as_posix()}"
