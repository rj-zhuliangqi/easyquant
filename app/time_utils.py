"""时区与时间工具。

后端 trading_date / naive datetime 统一按北京时间存储与判断。
调度器（main.py:683）已用 Asia/Shanghai；其它零散调用收敛到 now_cn()。
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

_CN = ZoneInfo("Asia/Shanghai")


def now_cn() -> datetime:
    """返回带时区的当前北京时间（tzinfo=Asia/Shanghai）。"""
    return datetime.now(_CN)
