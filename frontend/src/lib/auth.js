const TOKEN_KEY = "eq_token";
const USERNAME_KEY = "eq_username";
const IS_ADMIN_KEY = "eq_is_admin";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token, username, isAdmin = false) {
  localStorage.setItem(TOKEN_KEY, token);
  if (username) localStorage.setItem(USERNAME_KEY, username);
  localStorage.setItem(IS_ADMIN_KEY, isAdmin ? "1" : "0");
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USERNAME_KEY);
  localStorage.removeItem(IS_ADMIN_KEY);
}

export function isAuthenticated() {
  return !!getToken();
}

export function getUsername() {
  return localStorage.getItem(USERNAME_KEY) || "";
}

export function isAdmin() {
  return localStorage.getItem(IS_ADMIN_KEY) === "1";
}
