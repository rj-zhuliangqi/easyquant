<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { setToken } from "../lib/auth";

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
        <Transition name="error-slide">
          <p v-if="error" class="login-error">{{ error }}</p>
        </Transition>
        <button type="submit" class="login-btn" :disabled="loading">
          <span v-if="loading" class="btn-spinner"></span>
          <span v-else>登 录</span>
        </button>
      </form>
    </div>
    <div class="login-decoration">
      <div class="deco-circle"></div>
      <div class="deco-circle"></div>
      <div class="deco-circle"></div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--bg);
  overflow: hidden;
}

.login-page::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 60% 40% at 20% 30%, rgba(6, 182, 212, 0.06), transparent),
    radial-gradient(ellipse 50% 30% at 80% 70%, rgba(139, 92, 246, 0.04), transparent);
  pointer-events: none;
}

.login-card {
  position: relative;
  z-index: 1;
  width: 400px;
  padding: 48px 40px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  backdrop-filter: blur(12px);
  animation: cardEnter 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes cardEnter {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.login-brand {
  text-align: center;
  margin-bottom: 36px;
}

.login-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  margin: 0 auto 16px;
  background: linear-gradient(135deg, var(--accent), #0891b2);
  border-radius: var(--radius-lg);
  color: #fff;
  font-weight: 800;
  font-size: 22px;
  box-shadow: 0 4px 16px rgba(6, 182, 212, 0.3);
}

.login-brand h1 {
  margin: 0;
  color: var(--text);
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.login-brand p {
  margin: 6px 0 0;
  color: var(--text-muted);
  font-size: 14px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}

.form-group input {
  padding: 12px 16px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text);
  font-size: 14px;
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.form-group input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.form-group input::placeholder {
  color: var(--text-disabled);
}

.login-error {
  margin: 0;
  padding: 10px 14px;
  background: var(--danger-soft);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: var(--radius-md);
  color: #fca5a5;
  font-size: 13px;
}

.error-slide-enter-active,
.error-slide-leave-active {
  transition: all var(--transition-fast);
}

.error-slide-enter-from,
.error-slide-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.login-btn {
  padding: 12px;
  background: linear-gradient(135deg, var(--accent), #0891b2);
  border: none;
  border-radius: var(--radius-md);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
}

.login-btn:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(6, 182, 212, 0.3);
}

.login-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.btn-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Decorative elements */
.login-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.deco-circle {
  position: absolute;
  border-radius: 50%;
  opacity: 0.03;
  border: 1px solid var(--accent);
}

.deco-circle:nth-child(1) {
  width: 400px;
  height: 400px;
  top: -100px;
  right: -100px;
}

.deco-circle:nth-child(2) {
  width: 300px;
  height: 300px;
  bottom: -80px;
  left: -80px;
}

.deco-circle:nth-child(3) {
  width: 200px;
  height: 200px;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  opacity: 0.02;
}

@media (max-width: 640px) {
  .login-card {
    width: calc(100% - 32px);
    max-width: 360px;
    padding: 32px 24px;
  }
}
</style>
