export function formatDateTime(value) {
  if (!value) return "--";
  return String(value).replace("T", " ").slice(0, 16);
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
