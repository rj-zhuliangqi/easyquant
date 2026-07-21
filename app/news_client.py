"""三源实时资讯抓取 — 东财 7×24 / 同花顺直播 / 新浪滚动。

设计原则：
- 直连 HTTP，**不走 akshare 中间层**（参考 ~/.claude/skills/a-stock-data 在 V3.0
  弃用 akshare 的理由：pandas 兼容性 / 版本踩坑多）。
- 仅依赖 ``requests``，与 :mod:`app.akshare_client` 风格一致；不引入新依赖
  （``httpx`` / ``tenacity``）。
- 节流：模块级时间戳，``MIN_INTERVAL_SECONDS = 0.6`` + 随机抖动，遵守东财
  防封铁律 (QPS ≤ 2)。源间额外 sleep 0.5s。
- 重试：手写指数退避 3 次，2 ** attempt 秒。
- 单源失败 ``raise``，由 :mod:`app.services.news_service` 层 try/except 隔离。

每个 fetcher 统一返回 ``list[NormalizedNewsItem]``，service 层只关心规范字段，
不关心源差异。
"""

from __future__ import annotations

import hashlib
import logging
import random
import time
from datetime import datetime
from typing import TypedDict

import requests


logger = logging.getLogger(__name__)


class NormalizedNewsItem(TypedDict, total=False):
    """归一化后的资讯条目；service 层只关心这些字段。"""

    source: str  # "eastmoney_724" / "ths_live" / "sina_roll"
    source_id: str  # 源侧唯一 ID
    title: str
    summary: str
    url: str
    published_at: datetime  # Asia/Shanghai naive datetime
    raw: dict  # 原始单条响应，调试用


# 防封：东财所有 np-* 接口 QPS ≤ 2、避免并发
MIN_INTERVAL_SECONDS = 0.6

# 模块级时间戳记账，确保跨调用之间也节流
_last_call_at: list[float] = [0.0]

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _build_session() -> requests.Session:
    """共享 Session，复用 TCP 连接 + 默认 header。"""

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": _USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
    )
    return session


_session = _build_session()


def _throttle() -> None:
    """两次外部请求之间至少间隔 ``MIN_INTERVAL_SECONDS`` 秒 + 100~300ms 抖动。"""

    now = time.monotonic()
    elapsed = now - _last_call_at[0]
    wait = MIN_INTERVAL_SECONDS - elapsed
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.3))
    _last_call_at[0] = time.monotonic()


def _retry_get(url: str, *, params: dict | None = None, headers: dict | None = None,
               attempts: int = 3, timeout: float = 10.0) -> dict:
    """GET + 自动节流 + 指数退避重试。

    重试条件：连接错误、超时、5xx、空 JSON。每次失败 sleep 2 ** attempt 秒。
    """

    last_err: Exception | None = None
    for attempt in range(attempts):
        try:
            _throttle()
            response = _session.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            if not data:
                raise ValueError("empty json response")
            return data
        except (requests.RequestException, ValueError) as exc:
            last_err = exc
            backoff = 2 ** attempt
            logger.warning(
                "news_client retry %d/%d for %s: %s; sleeping %.1fs",
                attempt + 1, attempts, url, exc, backoff,
            )
            time.sleep(backoff)
    assert last_err is not None
    raise last_err


# ---- 源 1：东方财富 7×24 快讯 ----------------------------------------------------

_EASTMONEY_URL = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
_EASTMONEY_HEADERS = {"Referer": "https://kuaixun.eastmoney.com/"}


def fetch_eastmoney_724(page_size: int = 200) -> list[NormalizedNewsItem]:
    """抓东方财富 7×24 快讯。

    端点：https://kuaixun.eastmoney.com/7_24.html
    必带 ``Referer``，否则会返回风控页面（HTML 而非 JSON）。
    """

    params = {
        "client": "web",
        "biz": "web_724",
        "fastColumn": "102",
        "sortEnd": "",
        "pageSize": str(page_size),
        "req_trace": hashlib.md5(str(time.time()).encode()).hexdigest()[:12],
    }
    data = _retry_get(_EASTMONEY_URL, params=params, headers=_EASTMONEY_HEADERS)

    items_raw = (data.get("data") or {}).get("fastNewsList") or []
    items: list[NormalizedNewsItem] = []
    for item in items_raw:
        code = item.get("code")
        title = (item.get("title") or "").strip()
        if not code or not title:
            continue
        show_time = item.get("showTime") or ""
        try:
            published_at = datetime.strptime(show_time, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        url = f"https://finance.eastmoney.com/a/{code}.html"
        items.append(
            NormalizedNewsItem(
                source="eastmoney_724",
                source_id=str(code),
                title=title,
                summary=(item.get("summary") or "").strip(),
                url=url,
                published_at=published_at,
                raw=item,
            )
        )
    return items


# ---- 源 2：同花顺财经直播 -------------------------------------------------------

_THS_URL = "https://news.10jqka.com.cn/tapp/news/push/stock/"
_THS_HEADERS = {"Referer": "https://news.10jqka.com.cn/"}


def fetch_ths_live(page: int = 1, page_size: int = 50) -> list[NormalizedNewsItem]:
    """抓同花顺财经直播（带题材归因 tagInfo）。

    端点：https://news.10jqka.com.cn/realtimenews.html
    """

    params = {"page": str(page), "tag": "", "track": "website", "pagesize": str(page_size)}
    data = _retry_get(_THS_URL, params=params, headers=_THS_HEADERS)

    items_raw = (data.get("data") or {}).get("list") or []
    items: list[NormalizedNewsItem] = []
    for item in items_raw:
        seq = item.get("seq") or item.get("id")
        title = (item.get("title") or "").strip()
        if not seq or not title:
            continue
        try:
            published_at = datetime.fromtimestamp(int(item.get("ctime", 0)))
        except (TypeError, ValueError):
            continue
        items.append(
            NormalizedNewsItem(
                source="ths_live",
                source_id=str(seq),
                title=title,
                summary=(item.get("digest") or item.get("short") or "").strip(),
                url=item.get("url") or "",
                published_at=published_at,
                raw=item,
            )
        )
    return items


# ---- 源 3：新浪财经滚动新闻 -----------------------------------------------------

_SINA_URL = "https://feed.mix.sina.com.cn/api/roll/get"


def fetch_sina_roll(num: int = 100) -> list[NormalizedNewsItem]:
    """抓新浪财经滚动新闻。

    pageid=155, lid=1686 为新浪财经「全部财经新闻」滚动流。
    """

    params = {"pageid": "155", "lid": "1686", "num": str(num), "page": "1"}
    data = _retry_get(_SINA_URL, params=params)

    items_raw = (data.get("result") or {}).get("data") or []
    items: list[NormalizedNewsItem] = []
    for item in items_raw:
        url = item.get("url") or item.get("wapurl") or ""
        title = (item.get("title") or item.get("stitle") or "").strip()
        if not url or not title:
            continue
        # 新浪 docurl 较长，用 sha1[:16] 作为 source_id 保证稳定
        source_id = hashlib.sha1(url.encode()).hexdigest()[:16]
        try:
            published_at = datetime.fromtimestamp(int(item.get("ctime", 0)))
        except (TypeError, ValueError):
            continue
        items.append(
            NormalizedNewsItem(
                source="sina_roll",
                source_id=source_id,
                title=title,
                summary=(item.get("intro") or "").strip(),
                url=url,
                published_at=published_at,
                raw=item,
            )
        )
    return items
