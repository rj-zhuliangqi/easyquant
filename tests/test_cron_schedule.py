"""cron 调度时区 / day_of_week 回归测试。

背景：APScheduler 的 ``day_of_week`` 编号是 0=Mon..6=Sun，与 Python
``datetime.weekday()`` 一致；而 POSIX cron 是 0=Sun..6=Sat。历史代码按
POSIX 语义写 ``1-5`` 当"周一到周五"，APScheduler 却读成"周二到周六"，
导致 8:20 盘前任务周一不跑、周六跑（见 2026-07 调查）。修正后 cron 统一用
``0-4`` 表 Mon-Fri、``4`` 表 Friday，catch-up 判定改用 ``_cron_dow_matches``
（identity 映射，不再 off-by-one）。

本测试直接对每个 BUILTIN_AI_JOBS 的 cron 构建 ``CronTrigger(timezone=
Asia/Shanghai)``，枚举一周实际触发的工作日，断言与意图一致 -- 任何方向
的 off-by-one 都会立刻挂。
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pytest
from apscheduler.triggers.cron import CronTrigger

from app.ai_center_registry import BUILTIN_AI_JOBS
from app.main import _cron_dow_matches
from app.main import _parse_cron_to_aps_kwargs

_SH = ZoneInfo("Asia/Shanghai")
# 2026-07-06 是周一（weekday=0），作为枚举起点
_MON = dt.datetime(2026, 7, 6, 0, 0, tzinfo=_SH)


def _fire_weekdays(cron_expr: str, *, days: int = 14) -> set[int]:
    """枚举 cron 在 ``days`` 天内实际触发的工作日集合（Mon=0..Sun=6）。"""
    kwargs = _parse_cron_to_aps_kwargs(cron_expr)
    trigger = CronTrigger(timezone=_SH, **kwargs)
    weekdays: set[int] = set()
    nxt = _MON
    end = _MON + dt.timedelta(days=days)
    while nxt < end:
        fire = trigger.get_next_fire_time(None, nxt)
        if fire is None or fire >= end:
            break
        weekdays.add(fire.weekday())
        nxt = fire + dt.timedelta(minutes=1)
    return weekdays


# ---------------------------------------------------------------------------
# _parse_cron_to_aps_kwargs
# ---------------------------------------------------------------------------

def test_parse_cron_to_aps_kwargs_basic():
    assert _parse_cron_to_aps_kwargs("20 8 * * 0-4") == {
        "minute": "20",
        "hour": "8",
        "day": "*",
        "month": "*",
        "day_of_week": "0-4",
    }


@pytest.mark.parametrize("bad", ["20 8 * *", "20 8 * * 1-5 extra", ""])
def test_parse_cron_to_aps_kwargs_rejects_non_5_field(bad):
    with pytest.raises(ValueError):
        _parse_cron_to_aps_kwargs(bad)


# ---------------------------------------------------------------------------
# _cron_dow_matches
# ---------------------------------------------------------------------------

def test_cron_dow_matches_star():
    for wd in range(7):
        assert _cron_dow_matches("*", wd) is True


def test_cron_dow_matches_mon_fri_range():
    # "0-4" 表 Mon-Fri：周一到周五命中，周六周日不命中
    assert _cron_dow_matches("0-4", 0) is True   # Mon
    assert _cron_dow_matches("0-4", 4) is True   # Fri
    assert _cron_dow_matches("0-4", 5) is False  # Sat  <- 旧 bug 在此命中
    assert _cron_dow_matches("0-4", 6) is False  # Sun


def test_cron_dow_matches_single_friday():
    assert _cron_dow_matches("4", 4) is True   # Fri
    assert _cron_dow_matches("4", 3) is False  # Thu
    assert _cron_dow_matches("4", 5) is False  # Sat


def test_cron_dow_matches_list():
    assert _cron_dow_matches("0,2,4", 0) is True
    assert _cron_dow_matches("0,2,4", 1) is False
    assert _cron_dow_matches("0,2,4", 2) is True
    assert _cron_dow_matches("0,2,4", 4) is True


# ---------------------------------------------------------------------------
# 关键回归：BUILTIN_AI_JOBS 每个 cron 实际触发的工作日 == 意图
# ---------------------------------------------------------------------------

def _intended_weekdays(dow_expr: str) -> set[int]:
    """cron dow 字段意图触发的工作日（与 _cron_dow_matches 同源语义）。"""
    return {wd for wd in range(7) if _cron_dow_matches(dow_expr, wd)}


@pytest.mark.parametrize("job", BUILTIN_AI_JOBS, ids=[j["job_name"] for j in BUILTIN_AI_JOBS])
def test_builtin_cron_fires_on_intended_weekdays(job):
    """每个内置 job 的 CronTrigger 实际触发工作日必须与 dow 字段意图一致。"""
    cron = job["schedule_rrule_or_cron"]
    dow = _parse_cron_to_aps_kwargs(cron)["day_of_week"]
    actual = _fire_weekdays(cron)
    intended = _intended_weekdays(dow)
    assert actual == intended, (
        f"{job['job_name']} cron={cron!r} dow={dow!r}: "
        f"actual weekdays={sorted(actual)} intended={sorted(intended)}"
    )


def test_weekday_jobs_fire_mon_to_fri_not_weekend():
    """11 个工作日 job（cron 末位 0-4）必须 Mon-Fri 触发，不含 Sat/Sun。

    这正是 2026-07 事故的根因：旧 cron ``1-5`` 被 APScheduler 读成 Tue-Sat。
    """
    weekday_jobs = [j for j in BUILTIN_AI_JOBS if j["schedule_rrule_or_cron"].endswith("0-4")]
    assert len(weekday_jobs) == 11, f"期望 11 个工作日 job，实际 {len(weekday_jobs)}"
    for job in weekday_jobs:
        actual = _fire_weekdays(job["schedule_rrule_or_cron"])
        assert actual == {0, 1, 2, 3, 4}, (
            f"{job['job_name']} 应只在 Mon-Fri 触发，实际={sorted(actual)}"
        )


def test_weekly_job_fires_only_friday():
    """周五 22:00 周报 job 必须只在 Friday 触发（weekday=4）。"""
    weekly = [j for j in BUILTIN_AI_JOBS if j["job_type"] == "weekly_review"]
    assert len(weekly) == 1
    job = weekly[0]
    assert job["schedule_rrule_or_cron"] == "0 22 * * 4"
    actual = _fire_weekdays(job["schedule_rrule_or_cron"], days=21)
    assert actual == {4}, f"{job['job_name']} 应只在周五触发，实际={sorted(actual)}"


# ---------------------------------------------------------------------------
# 原 bug 的精确复现：08:20 盘前任务周一跑、周六不跑
# ---------------------------------------------------------------------------

def test_0820_premarket_fires_monday_not_saturday():
    """08:20 盘前消息面挖掘：周一必须触发，周六周日必须不触发。"""
    job = next(j for j in BUILTIN_AI_JOBS if j["job_name"].startswith("08:20"))
    actual = _fire_weekdays(job["schedule_rrule_or_cron"])
    assert 0 in actual, "08:20 任务必须在周一触发（旧 bug 下周一不跑）"
    assert 5 not in actual, "08:20 任务不应在周六触发（旧 bug 下周六跑）"
    assert 6 not in actual, "08:20 任务不应在周日触发"


def test_0820_premarket_fire_time_is_0820_shanghai():
    """08:20 任务的触发时刻必须是上海时间 08:20，且落在工作日。"""
    job = next(j for j in BUILTIN_AI_JOBS if j["job_name"].startswith("08:20"))
    kwargs = _parse_cron_to_aps_kwargs(job["schedule_rrule_or_cron"])
    trigger = CronTrigger(timezone=_SH, **kwargs)
    # 从周一 00:00 找第一次触发
    fire = trigger.get_next_fire_time(None, _MON)
    assert fire is not None
    assert fire.weekday() == 0, f"第一次触发应在周一，实际 {fire.strftime('%a')}"
    assert (fire.hour, fire.minute) == (8, 20), f"应在 08:20 触发，实际 {fire:%H:%M}"
    assert fire.utcoffset() == dt.timedelta(hours=8), "触发时间必须是 +08:00 上海时区"
