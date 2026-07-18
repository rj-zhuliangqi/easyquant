/** 返回本地时区的 YYYY-MM-DD（全站唯一 todayIso 实现）。
 * 后端 trading_date 用 naive 北京时间，故这里用本地时区而非 UTC，
 * 避免 0:00-8:00 之间预热 key 与页面 key 对不上（P2-7）。 */
export function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function formatDateTime(value) {
  if (!value) return "--";
  return String(value).replace("T", " ").slice(0, 16);
}

export function formatRelativeTime(value) {
  if (!value) return "--";
  const target = new Date(value);
  if (Number.isNaN(target.getTime())) return "--";
  const diffMs = Date.now() - target.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return "刚刚";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} 分钟前`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour} 小时前`;
  return formatDateTime(value);
}

export function formatPercent(value, digits = 2) {
  if (value == null || Number.isNaN(Number(value))) return "--";
  const numeric = Number(value);
  return `${numeric > 0 ? "+" : ""}${numeric.toFixed(digits)}%`;
}

export function formatNumber(value, digits = 2) {
  if (value == null || Number.isNaN(Number(value))) return "--";
  return Number(value).toLocaleString("zh-CN", {
    maximumFractionDigits: digits,
  });
}

export function formatAmount(value, digits = 2) {
  if (value == null || Number.isNaN(Number(value))) return "--";
  const numeric = Number(value);
  const sign = numeric > 0 ? "+" : numeric < 0 ? "-" : "";
  const absolute = Math.abs(numeric);
  if (absolute >= 100000000) return `${sign}${(absolute / 100000000).toFixed(digits)}亿`;
  if (absolute >= 10000) return `${sign}${(absolute / 10000).toFixed(digits)}万`;
  return `${sign}${absolute.toFixed(digits)}`;
}
