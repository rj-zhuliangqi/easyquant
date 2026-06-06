<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { setToken } from "../lib/auth";
import { fetchJson } from "../lib/api";

const router = useRouter();
const username = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);

async function handleLogin() {
  error.value = "";
  if (!username.value.trim() || !password.value) {
    error.value = "请输入用户名和密码";
    return;
  }
  loading.value = true;
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: username.value.trim(), password: password.value }),
    });
    const data = await res.json();
    if (!res.ok) {
      error.value = data.detail || "登录失败";
      return;
    }
    setToken(data.access_token, data.username, data.is_admin);
    router.push("/");
  } catch (e) {
    error.value = "网络错误，请重试";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <div class="login-mark">EQ</div>
        <h1>EasyQuant</h1>
        <p>盘中工作台</p>
      </div>
      <form class="login-form" @submit.prevent="handleLogin">
        <div class="form-group">
          <label for="username">用户名</label>
          <input
            id="username"
            v-model="username"
            type="text"
            placeholder="请输入用户名"
            autocomplete="username"
            autofocus
          />
        </div>
        <div class="form-group">
          <label for="password">密码</label>
          <input
            id="password"
            v-model="password"
            type="password"
            placeholder="请输入密码"
            autocomplete="current-password"
          />
        </div>
        <p v-if="error" class="login-error">{{ error }}</p>
        <button type="submit" class="login-btn" :disabled="loading">
          {{ loading ? "登录中..." : "登 录" }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
}

.login-card {
  width: 380px;
  padding: 40px 36px;
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 16px;
  backdrop-filter: blur(12px);
}

.login-brand {
  text-align: center;
  margin-bottom: 32px;
}

.login-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  margin: 0 auto 12px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border-radius: 12px;
  color: #fff;
  font-weight: 800;
  font-size: 20px;
}

.login-brand h1 {
  margin: 0;
  color: #f1f5f9;
  font-size: 22px;
  font-weight: 700;
}

.login-brand p {
  margin: 4px 0 0;
  color: #94a3b8;
  font-size: 13px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 13px;
  color: #cbd5e1;
  font-weight: 500;
}

.form-group input {
  padding: 10px 14px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 8px;
  color: #f1f5f9;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

.form-group input:focus {
  border-color: #6366f1;
}

.form-group input::placeholder {
  color: #64748b;
}

.login-error {
  margin: 0;
  padding: 8px 12px;
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 6px;
  color: #fca5a5;
  font-size: 13px;
}

.login-btn {
  padding: 10px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}

.login-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.login-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
