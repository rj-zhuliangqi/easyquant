import { router } from "../router";
import { getToken, clearToken } from "./auth";

/** 401 时跳登录页，保留 SPA 状态（避免整页刷新）；login 页自身不跳防循环 */
function redirectToLogin() {
  clearToken();
  if (router.currentRoute.value?.name !== "login") {
    router.push({ name: "login" });
  }
}

export async function fetchJson(url, options = {}) {
  const token = getToken();
  const headers = { ...(options.headers || {}) };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  // 透传 options.signal 供 vue-query 取消请求（P2-8f）
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) {
    redirectToLogin();
    throw new Error("登录已过期，请重新登录");
  }
  if (!response.ok) {
    let detail = "";
    const ct = response.headers.get("content-type") || "";
    if (ct.includes("application/json")) {
      try {
        const payload = await response.json();
        if (payload?.detail) detail = `: ${payload.detail}`;
      } catch {
        // ignore JSON parsing failure
      }
    }
    throw new Error(`Request failed ${response.status}${detail}`);
  }
  // 检查 content-type 再 parse，避免非 JSON 200 抛未处理异常（P2-8g）
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return null;
  }
  return response.json();
}

/**
 * Fetch a Server-Sent Events stream from `url` and invoke `onChunk(eventPayload)`
 * for each parsed event. Supports POST + body via `options.body`.
 *
 * SSE format consumed:
 *   data: {"type":"delta","text":"..."}\n\n
 *   : ping\n\n                         ← heartbeat comment, ignored
 *   data: {"type":"done",...}\n\n
 *
 * Errors are thrown with a `name === "AbortError"` when the caller aborts via
 * `options.signal`, mirroring native fetch behaviour.
 */
export async function fetchStream(url, options = {}, onChunk) {
  const token = getToken();
  const headers = { ...(options.headers || {}) };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) {
    redirectToLogin();
    throw new Error("登录已过期，请重新登录");
  }
  if (!response.ok) {
    let detail = "";
    try {
      const payload = await response.json();
      if (payload?.detail) detail = `: ${payload.detail}`;
    } catch {
      // ignore JSON parsing failure
    }
    throw new Error(`Request failed ${response.status}${detail}`);
  }
  if (!response.body) {
    throw new Error("Response has no body");
  }
  if (typeof onChunk !== "function") {
    throw new Error("fetchStream requires onChunk callback");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const lines = rawEvent.split("\n");
      let dataLine = "";
      let isComment = true;
      for (const ln of lines) {
        if (ln.startsWith(":")) continue; // SSE comment / heartbeat
        isComment = false;
        if (ln.startsWith("data:")) dataLine += ln.slice(5).trim();
        // event:/id:/retry: are intentionally ignored — backend uses data: only
      }
      if (isComment || !dataLine) continue;
      try {
        onChunk(JSON.parse(dataLine));
      } catch {
        // skip malformed JSON chunks silently
      }
    }
  }
  // tail: 极少出现 — 单 chunk 没以 \n\n 结尾（已 EOF），尽力解析一次
  const trimmed = buffer.trim();
  if (trimmed.startsWith("data:")) {
    try {
      onChunk(JSON.parse(trimmed.slice(5).trim()));
    } catch {
      // ignore
    }
  }
}

export function pageQueryKey(pageName, params = {}) {
  return ["page", pageName, params];
}

// ---------- 选股器 (2026-07-22 重构) ----------
export async function fetchScreenerStrategies() {
  return fetchJson("/api/screener/strategies");
}

export async function fetchScreenerStock(code) {
  return fetchJson(`/api/screener/stocks/${encodeURIComponent(code)}`);
}

export async function runScreener(payload) {
  return fetchJson("/api/screener/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function saveScreenerPreset(payload) {
  return fetchJson("/api/screener/presets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteScreenerPreset(id) {
  return fetchJson(`/api/screener/presets/${id}`, { method: "DELETE" });
}

export async function runScreenerBacktest(payload) {
  return fetchJson("/api/screener/backtest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listStockPools() {
  return fetchJson("/api/screener/pools");
}

export async function saveStockPool(payload) {
  return fetchJson("/api/screener/pools", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function saveAlertRule(payload) {
  return fetchJson("/api/screener/alerts/rules", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listAlertEvents(days = 7) {
  return fetchJson(`/api/screener/alerts/events?days=${days}`);
}

export async function checkAlerts() {
  return fetchJson("/api/screener/alerts/check", { method: "POST" });
}

export async function fetchRealtimeNews({
  limit = 50,
  hours = 48,
  importance = 0,
  sort = "mixed",
  sources = [],
  industries = [],
  actions = [],
  sinceId = null,
} = {}) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  params.set("hours", String(hours));
  params.set("importance", String(importance));
  params.set("sort", sort);
  if (sources.length) params.set("sources", sources.join(","));
  if (industries.length) params.set("industries", industries.join(","));
  if (actions.length) params.set("actions", actions.join(","));
  if (sinceId != null) params.set("since_id", String(sinceId));
  return fetchJson(`/api/news/realtime?${params.toString()}`);
}
