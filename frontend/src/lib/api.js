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
