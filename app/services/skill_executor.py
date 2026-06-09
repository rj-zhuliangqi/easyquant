"""Skill 执行引擎抽象层

支持多种执行引擎（Claude Code CLI、Goose CLI、自定义脚本），
统一接口，便于在 APScheduler 中调度和前端管理。

用法:
    from app.services.skill_executor import get_executor, SkillExecutor

    executor = get_executor("claude-code")
    result = executor.execute(
        skill_name="尾盘选股",
        trading_date=date(2026, 6, 7),
        data_file="/tmp/easyquant_market_data_2026-06-07.json",
        output_dir="/Users/jwkj/easyquant/data/ai_center/inbox",
        config={"model": "opus", "timeout_s": 300},
    )
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
INBOX_DIR = PROJECT_DIR / "data" / "ai_center" / "inbox"
FETCH_DATA_SCRIPT = PROJECT_DIR / "scripts" / "fetch_data.py"


@dataclass
class ExecuteResult:
    """执行结果"""
    success: bool = False
    skill_name: str = ""
    trading_date: str = ""
    engine_type: str = ""
    duration_ms: int = 0
    output_files: list[str] = field(default_factory=list)
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class SkillExecutor(Protocol):
    """执行引擎抽象接口"""

    def execute(
        self,
        *,
        skill_name: str,
        trading_date: date,
        data_file: str,
        output_dir: str,
        config: dict[str, Any],
        skill_prompt: str | None = None,
    ) -> ExecuteResult: ...


def _build_prompt(
    skill_name: str,
    trading_date: date,
    data_file: str,
    output_dir: str,
    engine_type: str,
    skill_prompt: str | None = None,
) -> str:
    """构建统一的执行 prompt"""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    safe_name = skill_name.replace(":", "").replace(" ", "_")
    output_path = f"{output_dir}/{safe_name}_{trading_date}_{timestamp}.json"

    base_prompt = skill_prompt or f"你正在执行选股策略「{skill_name}」，交易日为 {trading_date}。"

    return f"""{base_prompt}

请按照以下步骤操作：

1. 读取预取数据文件: {data_file}
   - 如果文件不存在或数据不完整，通过以下方式补充数据（按优先级）：
     a. 调用本地API: curl -s http://127.0.0.1:8010/api/overview | python3 -m json.tool
     b. 调用东方财富API: curl -s 'https://push2.eastmoney.com/api/qt/clist/get?...'
     c. 调用腾讯财经: curl -s 'https://qt.gtimg.cn/q=...'
     d. 使用AKShare: python3 -c 'import akshare as ak; ...'

2. 根据策略逻辑分析数据

3. 将分析结果输出为 JSON 文件，写入:
   {output_path}

   **重要：raw_output 字段必须使用 HTML 格式书写，用于前端直接渲染展示。要求如下：**
   - 使用语义化 HTML 标签: <h2>章节标题</h2>, <h3>子标题</h3>
   - 板块涨跌排行用 <table>，三列: <th>排名</th><th>板块</th><th>涨跌幅</th>
   - 涨幅用 <span class="up">+7.9%</span>，跌幅用 <span class="down">-3.4%</span>
   - 涨停用 <span class="limit-up">涨停</span>，跌停用 <span class="limit-down">跌停</span>
   - 关键股票名用 <b>加粗</b>，核心结论用 <b>加粗</b>
   - 风险提示用 <div class="risk-box">包裹</div>
   - 章节之间用 <hr> 分隔
   - 不要包含 <html><head><body> 等外层标签，只写内容片段
   - 所有 HTML 属性用双引号，确保在 JSON 字符串中合法

   JSON 必须严格遵循以下格式:
   {{
     "trading_date": "{trading_date}",
     "skill_name": "{skill_name}",
     "job_name": "{skill_name}",
     "job_type": "stock_pick",
     "run_type": "production",
     "source_input_ref": "{engine_type}-cli",
     "_meta": {{
       "schema_version": "3.0",
       "engine_type": "{engine_type}",
       "data_sources_used": ["..."]
     }},
     "summary": {{
       "market_phase": "...",
       "hot_sectors": [...],
       "risk_signals": [...]
     }},
     "result_payload": {{
       "structured_picks": [
         {{
           "stock_code": "000000",
           "stock_name": "示例",
           "pick_level": "strong_recommend",
           "reason_summary": "选股理由摘要",
           "reason_detail": "详细分析过程...",
           "sector_name": "所属板块",
           "theme_tags": ["主题1", "主题2"],
           "capital_profile": {{"net_inflow": 0.0, "main_force_signal": "strong"}},
           "signal_context": "信号上下文描述",
           "risk_flags": ["风险提示1"],
           "entry_hint": "入场建议",
           "confidence_score": 0.8
         }}
       ]
     }},
     "raw_output": "完整分析过程原文..."
   }}

   注意:
   - structured_picks 中的每个 pick 必须包含全部 12 个字段
   - pick_level 可选值: watch / candidate / confirm / strong_recommend
   - theme_tags 和 risk_flags 必须是非空数组
   - capital_profile 必须是非空对象
   - 如果没有找到符合条件的股票，structured_picks 可以为空数组"""


class ClaudeCodeExecutor:
    """Claude Code CLI 执行器"""

    def execute(
        self,
        *,
        skill_name: str,
        trading_date: date,
        data_file: str,
        output_dir: str,
        config: dict[str, Any],
        skill_prompt: str | None = None,
    ) -> ExecuteResult:
        prompt = _build_prompt(skill_name, trading_date, data_file, output_dir, "claude-code", skill_prompt)
        timeout = config.get("timeout_s", 1800)

        claude_path = _find_cli("claude")
        if not claude_path:
            return ExecuteResult(
                success=False,
                skill_name=skill_name,
                trading_date=trading_date.isoformat(),
                engine_type="claude-code",
                error="claude CLI not found in PATH or common install locations",
            )

        cmd = [
            claude_path, "-p", prompt,
            "--allowedTools", "Bash(curl*)", "Bash(python*)", "Write", "Read", "WebFetch",
            "--output-format", "text",
        ]

        logger.info("Executing skill '%s' via claude-code (timeout=%ds)", skill_name, timeout)
        start = time.time()

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = proc.communicate(timeout=timeout)
            duration_ms = int((time.time() - start) * 1000)

            if proc.returncode != 0:
                logger.error("claude-code exited with code %d: stderr=%s stdout=%s",
                             proc.returncode, stderr[:500], stdout[:500])
                output_files = _find_new_output_files(output_dir, start)
                return ExecuteResult(
                    success=len(output_files) > 0,
                    skill_name=skill_name,
                    trading_date=trading_date.isoformat(),
                    engine_type="claude-code",
                    duration_ms=duration_ms,
                    output_files=output_files,
                    error=stderr[:1000] or stdout[:1000] if not output_files else None,
                )

            # Check for new output files
            output_files = _find_new_output_files(output_dir, start)
            if not output_files:
                logger.warning("claude-code returned 0 but produced no output files; stdout=%s",
                               stdout[:500])
            else:
                logger.info("claude-code completed in %dms, produced %d file(s)", duration_ms, len(output_files))

            return ExecuteResult(
                success=len(output_files) > 0,
                skill_name=skill_name,
                trading_date=trading_date.isoformat(),
                engine_type="claude-code",
                duration_ms=duration_ms,
                output_files=output_files,
                error=None if output_files else "No output files produced",
            )

        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                stdout, stderr = proc.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = (proc.stdout and proc.stdout.read()) or "", (proc.stderr and proc.stderr.read()) or ""
            duration_ms = int((time.time() - start) * 1000)
            # Check for partial output files even on timeout
            output_files = _find_new_output_files(output_dir, start)
            logger.error("claude-code timed out after %dms, output_files=%d, stdout=%s",
                         duration_ms, len(output_files), (stdout or "")[:200])
            if output_files:
                logger.info("claude-code produced %d file(s) before timeout — treating as partial success", len(output_files))
            return ExecuteResult(
                success=len(output_files) > 0,
                skill_name=skill_name,
                trading_date=trading_date.isoformat(),
                engine_type="claude-code",
                duration_ms=duration_ms,
                output_files=output_files,
                error=f"Timeout after {timeout}s" if not output_files else f"Timeout after {timeout}s but {len(output_files)} output files produced",
            )


class GooseExecutor:
    """Goose CLI 执行器"""

    def execute(
        self,
        *,
        skill_name: str,
        trading_date: date,
        data_file: str,
        output_dir: str,
        config: dict[str, Any],
        skill_prompt: str | None = None,
    ) -> ExecuteResult:
        prompt = _build_prompt(skill_name, trading_date, data_file, output_dir, "goose", skill_prompt)
        timeout = config.get("timeout_s", 1800)

        cmd = [
            "goose", "session", "run",
            "--name", f"{skill_name}_{trading_date}",
            "--prompt", prompt,
        ]

        logger.info("Executing skill '%s' via goose (timeout=%ds)", skill_name, timeout)
        start = time.time()

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration_ms = int((time.time() - start) * 1000)

            if proc.returncode != 0:
                logger.error("goose exited with code %d: %s", proc.returncode, proc.stderr[:500])
                return ExecuteResult(
                    success=False,
                    skill_name=skill_name,
                    trading_date=trading_date.isoformat(),
                    engine_type="goose",
                    duration_ms=duration_ms,
                    error=proc.stderr[:1000],
                )

            output_files = _find_new_output_files(output_dir, start)
            logger.info("goose completed in %dms, produced %d file(s)", duration_ms, len(output_files))

            return ExecuteResult(
                success=True,
                skill_name=skill_name,
                trading_date=trading_date.isoformat(),
                engine_type="goose",
                duration_ms=duration_ms,
                output_files=output_files,
            )

        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start) * 1000)
            return ExecuteResult(
                success=False,
                skill_name=skill_name,
                trading_date=trading_date.isoformat(),
                engine_type="goose",
                duration_ms=duration_ms,
                error=f"Timeout after {timeout}s",
            )
        except FileNotFoundError:
            return ExecuteResult(
                success=False,
                skill_name=skill_name,
                trading_date=trading_date.isoformat(),
                engine_type="goose",
                error="goose CLI not found in PATH",
            )


class CustomExecutor:
    """自定义脚本执行器"""

    def execute(
        self,
        *,
        skill_name: str,
        trading_date: date,
        data_file: str,
        output_dir: str,
        config: dict[str, Any],
        skill_prompt: str | None = None,
    ) -> ExecuteResult:
        command_template = config.get("command", "")
        if not command_template:
            return ExecuteResult(
                success=False,
                skill_name=skill_name,
                trading_date=trading_date.isoformat(),
                engine_type="custom",
                error="No command template configured",
            )

        timeout = config.get("timeout_s", 1800)

        # Replace placeholders
        cmd_str = command_template.format(
            skill_name=skill_name,
            trading_date=trading_date.isoformat(),
            data_file=data_file,
            output_dir=output_dir,
        )

        logger.info("Executing skill '%s' via custom command: %s", skill_name, cmd_str)
        start = time.time()

        try:
            proc = subprocess.run(
                cmd_str,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration_ms = int((time.time() - start) * 1000)

            output_files = _find_new_output_files(output_dir, start)

            return ExecuteResult(
                success=proc.returncode == 0,
                skill_name=skill_name,
                trading_date=trading_date.isoformat(),
                engine_type="custom",
                duration_ms=duration_ms,
                output_files=output_files,
                error=proc.stderr[:1000] if proc.returncode != 0 else None,
            )

        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start) * 1000)
            return ExecuteResult(
                success=False,
                skill_name=skill_name,
                trading_date=trading_date.isoformat(),
                engine_type="custom",
                duration_ms=duration_ms,
                error=f"Timeout after {timeout}s",
            )


def _find_new_output_files(output_dir: str, since_epoch: float) -> list[str]:
    """查找在 since_epoch 之后创建的 JSON 文件"""
    output_path = Path(output_dir)
    if not output_path.exists():
        return []

    files = []
    for f in output_path.glob("*.json"):
        try:
            if f.stat().st_mtime >= since_epoch:
                files.append(str(f))
        except OSError:
            continue
    return sorted(files)


def _find_cli(name: str) -> str | None:
    """Find the full path to a CLI tool, checking PATH and common install locations."""
    import shutil

    path = shutil.which(name)
    if path:
        return path

    home = Path.home()
    common_paths = [
        home / ".local" / "bin" / name,
        home / ".hermes" / "node" / "bin" / name,
        home / ".cargo" / "bin" / name,
        Path("/opt/homebrew/bin") / name,
        Path("/usr/local/bin") / name,
    ]
    for p in common_paths:
        if p.exists():
            return str(p)
    return None


def get_executor(engine_type: str) -> SkillExecutor:
    """根据引擎类型获取执行器实例"""
    executors = {
        "claude-code": ClaudeCodeExecutor,
        "goose": GooseExecutor,
        "custom": CustomExecutor,
    }
    cls = executors.get(engine_type)
    if cls is None:
        raise ValueError(f"Unknown engine type: {engine_type}. Available: {', '.join(executors.keys())}")
    return cls()


def prefetch_market_data(trading_date: date, output_file: str | None = None) -> str:
    """预取市场数据，返回输出文件路径"""
    if output_file is None:
        output_file = f"/tmp/easyquant_market_data_{trading_date.isoformat()}.json"

    cmd = [
        "python3",
        str(FETCH_DATA_SCRIPT),
        "--date", trading_date.isoformat(),
        "--output", output_file,
    ]

    logger.info("Prefetching market data for %s → %s", trading_date, output_file)
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception as exc:
        logger.warning("Market data prefetch failed: %s (skill will attempt direct API calls)", exc)

    return output_file
