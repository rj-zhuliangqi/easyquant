"""skill_executor 文件归属测试（B1）。

_find_new_output_files 带 name_prefix 时只认本 skill 约定文件名前缀的产物，
避免并发执行多个 skill 时按 mtime 抢占彼此文件。
"""
from __future__ import annotations

import time
from pathlib import Path

from app.services.skill_executor import _find_new_output_files


def test_find_new_files_filters_by_name_prefix(tmp_path: Path) -> None:
    """同时存在两个 skill 的产物时，name_prefix 只返回匹配前缀的文件。"""
    d = tmp_path / "inbox"
    d.mkdir()
    since = time.time() - 60  # 一分钟前作为起点

    # skill A 的产物
    (d / "早盘复盘_2026-07-18_20260718093000.json").write_text("{}", encoding="utf-8")
    # skill B 的产物（同时间窗口，不应被 A 抢走）
    (d / "盘中监控_2026-07-18_20260718093005.json").write_text("{}", encoding="utf-8")
    # 一个无前缀的杂散文件
    (d / "orphan_2026-07-18.json").write_text("{}", encoding="utf-8")

    # skill A 查找：只应返回早盘复盘那一个
    files_a = _find_new_output_files(str(d), since, name_prefix="早盘复盘_2026-07-18_")
    assert len(files_a) == 1, f"skill A 应只匹配自己的产物，实际 {files_a}"
    assert files_a[0].endswith("早盘复盘_2026-07-18_20260718093000.json")

    # skill B 查找：只应返回盘中监控那一个
    files_b = _find_new_output_files(str(d), since, name_prefix="盘中监控_2026-07-18_")
    assert len(files_b) == 1
    assert files_b[0].endswith("盘中监控_2026-07-18_20260718093005.json")


def test_find_new_files_without_prefix_keeps_legacy_behavior(tmp_path: Path) -> None:
    """不传 name_prefix 时保留旧行为：匹配所有 *.json（custom executor 依赖）。"""
    d = tmp_path / "inbox"
    d.mkdir()
    since = time.time() - 60

    (d / "any_skill_2026-07-18_x.json").write_text("{}", encoding="utf-8")
    (d / "another_2026-07-18_y.json").write_text("{}", encoding="utf-8")

    files = _find_new_output_files(str(d), since)
    assert len(files) == 2, f"无前缀应返回全部，实际 {files}"


def test_find_new_files_respects_since_epoch(tmp_path: Path) -> None:
    """since_epoch 之前的旧文件不应被返回。"""
    d = tmp_path / "inbox"
    d.mkdir()

    (d / "早盘复盘_2026-07-17_old.json").write_text("{}", encoding="utf-8")
    # 取一个比现在还晚的 since -> 不应命中任何文件
    future = time.time() + 60
    files = _find_new_output_files(str(d), future, name_prefix="早盘复盘_")
    assert files == []
