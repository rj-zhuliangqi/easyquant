import { getToken, clearToken } from "./auth";

export async function fetchJson(url, options = {}) {
  const token = getToken();
  const headers = { ...(options.headers || {}) };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) {
    clearToken();
    window.location.href = "/login";
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
  return response.json();
}

export function pageQueryKey(pageName, params = {}) {
  return ["page", pageName, params];
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
