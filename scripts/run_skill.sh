#!/usr/bin/env bash
# ============================================================================
# EasyQuant Skill Runner — 双引擎执行包装脚本
#
# 用法:
#   ./scripts/run_skill.sh [选项] <skill名称> [交易日期]
#
# 选项:
#   --engine claude|goose   执行引擎 (默认: claude)
#   --skip-fetch            跳过数据预取
#   --dry-run               只预取数据，不执行 skill
#   --timeout SECONDS       执行超时 (默认: 600)
#
# 示例:
#   ./scripts/run_skill.sh 尾盘选股
#   ./scripts/run_skill.sh --engine goose 超短线盘后选股 2026-06-07
#   ./scripts/run_skill.sh --skip-fetch --timeout 300 集合竞价分析
#   ./scripts/run_skill.sh --dry-run 尾盘选股
# ============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
ENGINE="claude"
SKIP_FETCH=false
DRY_RUN=false
TIMEOUT=600
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INBOX_DIR="${PROJECT_DIR}/data/ai_center/inbox"
LOG_DIR="${PROJECT_DIR}/data/logs"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --engine)
      ENGINE="$2"
      shift 2
      ;;
    --skip-fetch)
      SKIP_FETCH=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --timeout)
      TIMEOUT="$2"
      shift 2
      ;;
    --help|-h)
      sed -n '2,/^# =/p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
    *)
      break
      ;;
  esac
done

SKILL_NAME="${1:?Usage: run_skill.sh <skill_name> [trading_date]}"
TRADING_DATE="${2:-$(date +%Y-%m-%d)}"
DATA_FILE="/tmp/easyquant_market_data_${TRADING_DATE}.json"
LOG_FILE="${LOG_DIR}/skills.log"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
mkdir -p "${INBOX_DIR}" "${LOG_DIR}"

log() {
  local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [${SKILL_NAME}] $*"
  echo "$msg" | tee -a "$LOG_FILE"
}

# Validate engine
case "$ENGINE" in
  claude|goose) ;;
  *)
    log "ERROR: Unknown engine '${ENGINE}'. Use 'claude' or 'goose'."
    exit 1
    ;;
esac

log "=========================================="
log "Skill: ${SKILL_NAME}"
log "Engine: ${ENGINE}"
log "Trading date: ${TRADING_DATE}"
log "=========================================="

# ---------------------------------------------------------------------------
# Step 1: Data Prefetch
# ---------------------------------------------------------------------------
if [ "$SKIP_FETCH" = false ]; then
  log "Step 1: Fetching market data..."
  if python "${PROJECT_DIR}/scripts/fetch_data.py" --date "$TRADING_DATE" --output "$DATA_FILE" >> "$LOG_FILE" 2>&1; then
    log "Data fetched successfully → ${DATA_FILE}"
  else
    log "WARNING: Data fetch failed. Skill will attempt direct API calls."
  fi
else
  log "Step 1: SKIPPED (data prefetch disabled)"
fi

if [ "$DRY_RUN" = true ]; then
  log "Dry run mode — exiting after data fetch."
  exit 0
fi

# ---------------------------------------------------------------------------
# Step 2: Execute Skill via Agent Engine
# ---------------------------------------------------------------------------
log "Step 2: Executing skill '${SKILL_NAME}' via ${ENGINE}..."
START_EPOCH=$(date +%s)

# Build the prompt
PROMPT="你正在执行选股策略「${SKILL_NAME}」，交易日为 ${TRADING_DATE}。

请按照以下步骤操作：

1. 读取预取数据文件: ${DATA_FILE}
   - 如果文件不存在或数据不完整，通过以下方式补充数据（按优先级）：
     a. 调用本地API: curl -s http://127.0.0.1:8010/api/overview | python -m json.tool
     b. 调用东方财富API: curl -s 'https://push2.eastmoney.com/api/qt/clist/get?...'
     c. 调用腾讯财经: curl -s 'https://qt.gtimg.cn/q=...'
     d. 使用AKShare: python -c 'import akshare as ak; ...'

2. 根据策略逻辑分析数据

3. 将分析结果输出为 JSON 文件，写入:
   ${INBOX_DIR}/${SKILL_NAME}_${TRADING_DATE}_${TIMESTAMP}.json

   JSON 必须严格遵循以下格式:
   {
     \"trading_date\": \"${TRADING_DATE}\",
     \"skill_name\": \"${SKILL_NAME}\",
     \"job_name\": \"${SKILL_NAME}\",
     \"job_type\": \"stock_pick\",
     \"run_type\": \"production\",
     \"source_input_ref\": \"${ENGINE}-cli\",
     \"_meta\": {
       \"schema_version\": \"3.0\",
       \"engine_type\": \"${ENGINE}\",
       \"data_sources_used\": [\"...\"]
     },
     \"summary\": {
       \"market_phase\": \"...\",
       \"hot_sectors\": [...],
       \"risk_signals\": [...]
     },
     \"result_payload\": {
       \"structured_picks\": [
         {
           \"stock_code\": \"000000\",
           \"stock_name\": \"示例\"
           \"pick_level\": \"strong_recommend\",
           \"reason_summary\": \"选股理由摘要\",
           \"reason_detail\": \"详细分析过程...\",
           \"sector_name\": \"所属板块\",
           \"theme_tags\": [\"主题1\", \"主题2\"],
           \"capital_profile\": {\"net_inflow\": 0.0, \"main_force_signal\": \"strong\"},
           \"signal_context\": \"信号上下文描述\",
           \"risk_flags\": [\"风险提示1\"],
           \"entry_hint\": \"入场建议\",
           \"confidence_score\": 0.8
         }
       ]
     },
     \"raw_output\": \"完整分析过程原文...\"
   }

   注意:
   - structured_picks 中的每个 pick 必须包含全部 12 个字段
   - pick_level 可选值: watch / candidate / confirm / strong_recommend
   - theme_tags 和 risk_flags 必须是非空数组
   - capital_profile 必须是非空对象
   - 如果没有找到符合条件的股票，structured_picks 可以为空数组"

# Execute based on engine
case "$ENGINE" in
  claude)
    if ! command -v claude &>/dev/null; then
      log "ERROR: claude CLI not found in PATH"
      exit 1
    fi
    log "Running: claude -p \"...\" (timeout: ${TIMEOUT}s)"
    claude -p "$PROMPT" \
      --allowedTools "Bash(curl*)" "Bash(python*)" "Write" "Read" "WebFetch" \
      --output-format text \
      2>&1 | tee -a "$LOG_FILE" || true
    ;;

  goose)
    if ! command -v goose &>/dev/null; then
      log "ERROR: goose CLI not found in PATH"
      exit 1
    fi
    log "Running: goose session run (timeout: ${TIMEOUT}s)"
    goose session run \
      --name "${SKILL_NAME}_${TRADING_DATE}" \
      --prompt "$PROMPT" \
      2>&1 | tee -a "$LOG_FILE" || true
    ;;
esac

END_EPOCH=$(date +%s)
DURATION=$((END_EPOCH - START_EPOCH))
log "Agent execution completed in ${DURATION}s"

# ---------------------------------------------------------------------------
# Step 3: Verify Output
# ---------------------------------------------------------------------------
log "Step 3: Verifying output..."
INBOX_BEFORE_COUNT=$(find "$INBOX_DIR" -name "*.json" 2>/dev/null | wc -l | tr -d ' ')

# Check for new JSON files in inbox
NEW_FILES=()
while IFS= read -r f; do
  if [[ "$(basename "$f")" == *"${SKILL_NAME}"* || "$(stat -f "%Sm" -t "%Y%m%d_%H%M" "$f" 2>/dev/null || stat -c "%Y" "$f" 2>/dev/null)" -gt "${START_EPOCH}" ]]; then
    NEW_FILES+=("$f")
  fi
done < <(find "$INBOX_DIR" -name "*.json" -newer "$DATA_FILE" 2>/dev/null || true)

# Fallback: just check any new files
if [ ${#NEW_FILES[@]} -eq 0 ]; then
  INBOX_AFTER_COUNT=$(find "$INBOX_DIR" -name "*.json" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$INBOX_AFTER_COUNT" -gt "$INBOX_BEFORE_COUNT" ]; then
    log "New files detected in inbox (before: ${INBOX_BEFORE_COUNT}, after: ${INBOX_AFTER_COUNT})"
    # List the newest files
    find "$INBOX_DIR" -name "*.json" -maxdepth 1 | sort -r | head -n $((INBOX_AFTER_COUNT - INBOX_BEFORE_COUNT)) | while read -r f; do
      log "  → $(basename "$f")"
    done
  else
    log "WARNING: No new JSON files found in inbox!"
    log "  The skill may not have produced output. Check the agent output above."
  fi
else
  log "Found ${#NEW_FILES[@]} new output file(s):"
  for f in "${NEW_FILES[@]}"; do
    log "  → $(basename "$f")"
    # Validate JSON
    if python -c "import json; json.load(open('$f'))" 2>/dev/null; then
      log "    ✓ Valid JSON"
    else
      log "    ✗ Invalid JSON — file may be corrupted"
    fi
  done
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
log "=========================================="
log "Execution Summary"
log "  Skill: ${SKILL_NAME}"
log "  Engine: ${ENGINE}"
log "  Date: ${TRADING_DATE}"
log "  Duration: ${DURATION}s"
log "  Output files: ${#NEW_FILES[@]}"
log "  Inbox: ${INBOX_DIR}"
log "  Log: ${LOG_FILE}"
log "=========================================="

# Remind about inbox scan
log "Note: The inbox scanner runs every 2 minutes and will auto-import these files."
log "To manually trigger import: curl -X POST http://127.0.0.1:8010/api/ai/import-run -H 'Content-Type: application/json' -d @<json_file>"
