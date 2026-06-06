export async function fetchJson(url, options) {
  const response = await fetch(url, options);
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
