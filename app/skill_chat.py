"""D1: SSE 流式 skill-chat 抽自 main.py。

包含 Claude CLI 子进程的流式生成、心跳、兜底超时 watcher、草案提取等。
全部模块级函数（无 create_app 闭包依赖），便于独立测试与维护。
"""
from __future__ import annotations

import json
import logging
import queue
import re
import subprocess
import threading
import time

logger = logging.getLogger(__name__)

# _SKILL_CHAT_TIMEOUT_SECONDS: subprocess 兜底超时（远大于 cloudflared 100s 边缘空闲超时，
#   中间只要有 SSE delta/心跳流出，cloudflared 不会切断）
# _SKILL_CHAT_HEARTBEAT_SECONDS: SSE 注释行 ": ping\n\n" 周期，防止 cloudflared idle 切断
_SKILL_CHAT_TIMEOUT_SECONDS = 300
_SKILL_CHAT_HEARTBEAT_SECONDS = 15

# 系统 prompt 必须下沉到模块级，因为 helper 函数（_build_skill_chat_prompt 等）会在模块作用域调用
_SKILL_CHAT_SYSTEM_PROMPT = """你是一个专业的A股选股策略专家。请根据用户的需求，生成选股策略配置或回答策略相关问题。

如果用户要求创建新策略，请生成以下格式的JSON：

{
  "skill_name": "策略名称（简短）",
  "skill_category": "stock-pick|news-scan|review|stock-confirm|position-review|weekly-review",
  "description": "策略描述（一句话）",
  "revision_title": "版本标题",
  "revision_content": "策略执行逻辑的详细描述，包括选股条件、过滤规则、排序方式等",
  "job_name": "定时任务名称（如 09:30 某某选股）",
  "schedule_label": "显示标签（如 09:30）",
  "schedule_rrule_or_cron": "标准5字段cron表达式",
  "job_type": "stock_pick|news_scan|day_review|stock_confirm|position_review|weekly_review",
  "display_group": "盘前|盘中|盘后|夜间|周报",
  "result_schema_version": "2.0"
}

Cron表达式规则（标准5字段：分 时 日 月 星期）：
- 盘前任务：20 8 * * 1-5（工作日8:20）
- 盘中任务：26 9 * * 1-5（工作日9:26）
- 盘后任务：0 19 * * 1-5（工作日19:00）
- 夜间任务：0 20 * * 1-5（工作日20:00）
- 周报任务：0 22 * * 5（周五22:00）

请用中文回复，JSON配置放在代码块中。"""


def _build_skill_chat_prompt(history: list, message: str) -> str:
    """拼装 Claude CLI 单次调用的最终 prompt。"""
    conversation = []
    for h in history:
        if h.get("role") == "user":
            conversation.append(f"用户: {h.get('content', '')}")
        elif h.get("role") == "assistant":
            conversation.append(f"助手: {h.get('content', '')}")
    conversation_text = "\n".join(conversation)
    return f"""{_SKILL_CHAT_SYSTEM_PROMPT}

{conversation_text}

用户: {message}

请回复："""


def _extract_skill_draft(output: str):
    """从 Claude 文本输出中提取 ```json ... ``` 代码块作为 skill 草案。"""
    if not output:
        return None
    json_match = re.search(r'```json\s*(.*?)\s*```', output, re.DOTALL)
    if not json_match:
        json_match = re.search(r'```\s*(\{.*?\})\s*```', output, re.DOTALL)
    if not json_match:
        return None
    try:
        return json.loads(json_match.group(1))
    except json.JSONDecodeError:
        return None


def _skill_chat_event(payload: dict) -> bytes:
    """把 dict 序列化成 SSE `data: {...}\\n\\n` 字节流。"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


def _kill_proc(proc: subprocess.Popen | None) -> None:
    """安全终止 Claude 子进程并等待回收（用于客户端断开 / 兜底超时）。"""
    if proc is None:
        return
    if proc.poll() is None:
        try:
            proc.kill()
        except Exception:
            logger.exception("skill-chat: proc.kill() failed")
        try:
            proc.wait(timeout=5)
        except Exception:
            logger.exception("skill-chat: proc.wait() after kill failed")


def _skill_chat_kill_watcher(proc: subprocess.Popen, stop_event: threading.Event) -> None:
    """后台 watcher 线程：到 _SKILL_CHAT_TIMEOUT_SECONDS 兜底 kill 子进程。"""
    deadline = time.time() + _SKILL_CHAT_TIMEOUT_SECONDS
    while not stop_event.is_set():
        if time.time() >= deadline:
            logger.warning(
                "skill-chat: watcher reached timeout (%ds), killing proc",
                _SKILL_CHAT_TIMEOUT_SECONDS,
            )
            _kill_proc(proc)
            return
        # 1s 轮询间隔足以兜底（及时 kill 即可）
        if stop_event.wait(1.0):
            return
        if proc.poll() is not None:
            return


def _skill_chat_stream_generator(claude_path: str, cli_prompt: str):
    """SSE 流式生成器：按行读 Claude stdout，每行 yield delta；15s 一次心跳。"""
    start = time.time()
    full_output_chunks: list[str] = []
    proc: subprocess.Popen | None = None
    stop_event = threading.Event()
    watcher: threading.Thread | None = None
    timed_out = False

    try:
        try:
            proc = subprocess.Popen(
                [
                    claude_path, "-p", cli_prompt,
                    "--allowedTools", "Bash(curl*)", "Bash(python*)", "Write", "Read",
                    "--output-format", "text",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                text=True,
            )
        except OSError as exc:
            logger.exception("skill-chat: failed to spawn claude")
            yield _skill_chat_event({"type": "error", "message": f"无法启动 Claude CLI: {exc}"})
            yield _skill_chat_event({"type": "done", "response": "", "skill_draft": None, "duration_ms": 0})
            return

        watcher = threading.Thread(
            target=_skill_chat_kill_watcher,
            args=(proc, stop_event),
            daemon=True,
        )
        watcher.start()

        # 用独立线程阻塞读 stdout，主循环靠 queue.get(timeout) 驱动心跳，
        # 避免 readline 阻塞期间零心跳（cloudflared 100s 空闲 -> 524）。
        line_queue: "queue.Queue[str | None]" = queue.Queue()

        def _stdout_reader() -> None:
            try:
                for line in iter(proc.stdout.readline, ""):
                    line_queue.put(line)
            except Exception:
                logger.exception("skill-chat: stdout reader thread failed")
            finally:
                line_queue.put(None)  # EOF / 异常哨兵

        reader_thread = threading.Thread(target=_stdout_reader, daemon=True)
        reader_thread.start()

        try:
            while True:
                try:
                    line = line_queue.get(timeout=_SKILL_CHAT_HEARTBEAT_SECONDS)
                except queue.Empty:
                    # 阻塞读期间无输出 -> 主动发心跳，重置 cloudflared 空闲计时
                    yield b": ping\n\n"
                    continue
                if line is None:
                    break
                full_output_chunks.append(line)
                yield _skill_chat_event({"type": "delta", "text": line})
        except (GeneratorExit, ConnectionError):
            logger.info("skill-chat: client disconnected, killing proc")
            _kill_proc(proc)
            return
        finally:
            stop_event.set()

        if watcher and watcher.is_alive():
            watcher.join(timeout=1.0)
        _kill_proc(proc)

        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            logger.warning("skill-chat: proc.wait() timed out, killing")
            _kill_proc(proc)

        duration_ms = int((time.time() - start) * 1000)
        full_output = "".join(full_output_chunks)
        skill_draft = _extract_skill_draft(full_output)

        # watcher 兜底超时已 kill → returncode 不为 0
        if proc.returncode not in (0, None):
            stderr_text = (proc.stderr.read() if proc.stderr else "")[:500]
            if not full_output and "timed out" in stderr_text.lower():
                timed_out = True
            logger.error(
                "skill-chat: claude exit=%d duration=%dms stderr=%s",
                proc.returncode, duration_ms, stderr_text,
            )
            if timed_out:
                yield _skill_chat_event({
                    "type": "error",
                    "message": f"请求超时（{_SKILL_CHAT_TIMEOUT_SECONDS}s），请重试或简化需求描述。",
                })
            else:
                yield _skill_chat_event({
                    "type": "error",
                    "message": f"Claude 退出码 {proc.returncode}: {stderr_text}",
                })
            yield _skill_chat_event({
                "type": "done",
                "response": full_output or stderr_text or "执行出错",
                "skill_draft": None,
                "duration_ms": duration_ms,
            })
            return

        logger.info(
            "skill-chat (stream): completed duration=%dms output_length=%d has_draft=%s",
            duration_ms, len(full_output), bool(skill_draft),
        )
        yield _skill_chat_event({
            "type": "done",
            "response": full_output,
            "skill_draft": skill_draft,
            "duration_ms": duration_ms,
        })
    except GeneratorExit:
        _kill_proc(proc)
        raise
    except Exception as exc:
        logger.exception("skill-chat: unexpected error in stream generator")
        try:
            yield _skill_chat_event({"type": "error", "message": f"内部错误: {exc}"})
            duration_ms = int((time.time() - start) * 1000)
            yield _skill_chat_event({
                "type": "done",
                "response": "",
                "skill_draft": None,
                "duration_ms": duration_ms,
            })
        except GeneratorExit:
            _kill_proc(proc)
            raise
    finally:
        stop_event.set()
        if watcher and watcher.is_alive():
            watcher.join(timeout=1.0)
        _kill_proc(proc)
