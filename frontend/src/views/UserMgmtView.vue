<script setup>
import { ref, onMounted, computed } from "vue";
import { fetchJson } from "../lib/api";
import { isAdmin } from "../lib/auth";
import DataPanel from "../components/ui/DataPanel.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import StatusBadge from "../components/ui/StatusBadge.vue";
import { useTimerCleanup } from "../composables/useTimerCleanup";

const isAdminUser = computed(() => isAdmin());

const users = ref([]);
const loading = ref(false);
const error = ref("");

// Create user form
const showCreate = ref(false);
const newUsername = ref("");
const newPassword = ref("");
const newIsAdmin = ref(false);
const createError = ref("");

// Reset password
const resetUserId = ref(null);
const resetUsername = ref("");
const resetPassword = ref("");
const resetError = ref("");

// Change own password
const oldPassword = ref("");
const changeNewPassword = ref("");
const changeError = ref("");
const changeSuccess = ref("");
// C3: setTimeout 集中管理
const { later } = useTimerCleanup();

// Active tab
const activeTab = ref(isAdminUser.value ? "users" : "password");

async function loadUsers() {
  loading.value = true;
  error.value = "";
  try {
    const res = await fetchJson("/api/auth/users");
    users.value = res.users;
  } catch (e) {
    error.value = "加载用户列表失败";
  } finally {
    loading.value = false;
  }
}

async function createUser() {
  createError.value = "";
  if (!newUsername.value.trim() || !newPassword.value) {
    createError.value = "请填写用户名和密码";
    return;
  }
  try {
    await fetchJson("/api/auth/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: newUsername.value.trim(), password: newPassword.value, is_admin: newIsAdmin.value }),
    });
    newUsername.value = "";
    newPassword.value = "";
    newIsAdmin.value = false;
    showCreate.value = false;
    await loadUsers();
  } catch (e) {
    createError.value = e.message.replace("Request failed 400: ", "");
  }
}

async function toggleActive(user) {
  try {
    await fetchJson(`/api/auth/users/${user.id}/toggle-active`, { method: "POST" });
    await loadUsers();
  } catch (e) {
    error.value = e.message;
  }
}

async function deleteUser(user) {
  if (!confirm(`确定要删除用户 "${user.username}" 吗？此操作不可撤销。`)) return;
  try {
    await fetchJson(`/api/auth/users/${user.id}`, { method: "DELETE" });
    await loadUsers();
  } catch (e) {
    error.value = e.message;
  }
}

function startReset(user) {
  resetUserId.value = user.id;
  resetUsername.value = user.username;
  resetPassword.value = "";
  resetError.value = "";
}

async function doReset() {
  resetError.value = "";
  if (!resetPassword.value) {
    resetError.value = "请输入新密码";
    return;
  }
  try {
    await fetchJson(`/api/auth/users/${resetUserId.value}/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_password: resetPassword.value }),
    });
    resetUserId.value = null;
    await loadUsers();
  } catch (e) {
    resetError.value = e.message;
  }
}

async function changeOwnPassword() {
  changeError.value = "";
  changeSuccess.value = "";
  if (!oldPassword.value || !changeNewPassword.value) {
    changeError.value = "请填写旧密码和新密码";
    return;
  }
  try {
    await fetchJson("/api/auth/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ old_password: oldPassword.value, new_password: changeNewPassword.value }),
    });
    changeSuccess.value = "密码修改成功";
    oldPassword.value = "";
    changeNewPassword.value = "";
    later(() => { changeSuccess.value = ""; }, 3000);
  } catch (e) {
    changeError.value = e.message.replace("Request failed 400: ", "");
  }
}

onMounted(() => { if (isAdminUser.value) loadUsers(); });
</script>

<template>
  <div class="page settings-page">
    <!-- Tab switcher (admin only) -->
    <div v-if="isAdminUser" class="tab-bar">
      <button class="tab-btn" :class="{ active: activeTab === 'users' }" @click="activeTab = 'users'; loadUsers()">用户管理</button>
      <button class="tab-btn" :class="{ active: activeTab === 'password' }" @click="activeTab = 'password'">修改密码</button>
    </div>

    <!-- ============ Change Password ============ -->
    <div v-if="activeTab === 'password'" class="panel password-panel">
      <div class="panel-head">
        <h3>修改密码</h3>
        <p>修改你的登录密码</p>
      </div>
      <div class="password-form">
        <label class="field">
          <span class="field-label">旧密码</span>
          <input v-model="oldPassword" type="password" placeholder="输入当前密码" />
        </label>
        <label class="field">
          <span class="field-label">新密码</span>
          <input v-model="changeNewPassword" type="password" placeholder="输入新密码" />
        </label>
        <div v-if="changeError" class="msg msg-error">{{ changeError }}</div>
        <div v-if="changeSuccess" class="msg msg-ok">{{ changeSuccess }}</div>
        <button class="save-btn" @click="changeOwnPassword">保存修改</button>
      </div>
    </div>

    <!-- ============ User Management ============ -->
    <template v-if="activeTab === 'users' && isAdminUser">
      <div class="page-hero">
        <div>
          <p class="eyebrow">系统设置</p>
          <h2>用户管理</h2>
        </div>
        <button class="add-btn" @click="showCreate = true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          添加用户
        </button>
      </div>

      <div v-if="error" class="msg msg-error">{{ error }}</div>
      <div v-if="loading" class="empty-state">加载中...</div>

      <div v-else class="user-cards">
        <div v-for="user in users" :key="user.id" class="user-card panel">
          <div class="user-card-main">
            <div class="uc-avatar" :class="{ admin: user.is_admin }">{{ user.username.charAt(0).toUpperCase() }}</div>
            <div class="uc-info">
              <div class="uc-name">
                {{ user.username }}
                <StatusBadge :status="user.is_admin ? 'info' : 'neutral'" size="sm">
                  {{ user.is_admin ? '管理员' : '用户' }}
                </StatusBadge>
              </div>
              <div class="uc-meta">
                <StatusBadge :status="user.is_active ? 'success' : 'danger'" size="sm">
                  {{ user.is_active ? '启用' : '已禁用' }}
                </StatusBadge>
                <span class="uc-dot">·</span>
                <span>最后登录 {{ user.last_login_at ? new Date(user.last_login_at).toLocaleDateString('zh-CN') : '从未' }}</span>
              </div>
            </div>
          </div>
          <div class="uc-actions">
            <button class="act-btn" @click="startReset(user)" title="重置密码">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            </button>
            <button class="act-btn" :class="{ warn: user.is_active }" @click="toggleActive(user)" :title="user.is_active ? '禁用' : '启用'">
              <svg v-if="user.is_active" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            </button>
            <button class="act-btn danger" @click="deleteUser(user)" title="删除用户">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>
        </div>
        <EmptyState
          v-if="!users.length"
          title="暂无用户"
          description="点击上方按钮添加第一个用户"
        />
      </div>
    </template>

    <!-- ============ Modals ============ -->

    <!-- Create user -->
    <Teleport to="body">
      <Transition name="modal-overlay">
        <div v-if="showCreate" class="overlay" @click.self="showCreate = false">
          <Transition name="modal-card">
            <div v-if="showCreate" class="modal">
              <h3>添加用户</h3>
              <label class="field">
                <span class="field-label">用户名</span>
                <input v-model="newUsername" type="text" placeholder="为用户设置登录名" />
              </label>
              <label class="field">
                <span class="field-label">密码</span>
                <input v-model="newPassword" type="password" placeholder="设置初始密码" />
              </label>
              <label class="field check-field">
                <input v-model="newIsAdmin" type="checkbox" />
                <span>设为管理员</span>
              </label>
              <div v-if="createError" class="msg msg-error">{{ createError }}</div>
              <div class="modal-footer">
                <button class="btn-ghost" @click="showCreate = false">取消</button>
                <button class="save-btn" @click="createUser">创建</button>
              </div>
            </div>
          </Transition>
        </div>
      </Transition>
    </Teleport>

    <!-- Reset password -->
    <Teleport to="body">
      <Transition name="modal-overlay">
        <div v-if="resetUserId" class="overlay" @click.self="resetUserId = null">
          <Transition name="modal-card">
            <div v-if="resetUserId" class="modal">
              <h3>重置密码</h3>
              <p class="modal-desc">为 <strong>{{ resetUsername }}</strong> 设置新密码</p>
              <label class="field">
                <span class="field-label">新密码</span>
                <input v-model="resetPassword" type="password" placeholder="输入新密码" />
              </label>
              <div v-if="resetError" class="msg msg-error">{{ resetError }}</div>
              <div class="modal-footer">
                <button class="btn-ghost" @click="resetUserId = null">取消</button>
                <button class="save-btn" @click="doReset">确认重置</button>
              </div>
            </div>
          </Transition>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 780px;
}

/* --- Tabs --- */
.tab-bar {
  display: flex;
  gap: 4px;
  padding: 4px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-5);
}

.tab-btn {
  flex: 1;
  padding: 10px 0;
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-muted);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tab-btn.active {
  background: var(--accent-soft);
  color: var(--accent);
}

.tab-btn:hover:not(.active) {
  background: rgba(255, 255, 255, 0.03);
}

/* --- Password form --- */
.password-panel {
  padding: var(--space-6);
}

.password-form {
  max-width: 360px;
  display: grid;
  gap: var(--space-4);
  margin-top: var(--space-2);
}

/* --- Fields --- */
.field {
  display: grid;
  gap: 6px;
}

.field-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
}

.field input[type="text"],
.field input[type="password"] {
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg);
  color: var(--text);
  font-size: 14px;
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.field input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.field input::placeholder {
  color: var(--text-disabled);
}

.check-field {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
}

.check-field input {
  accent-color: var(--accent);
  width: 16px;
  height: 16px;
}

.check-field span {
  font-size: 14px;
  color: var(--text);
}

/* --- Messages --- */
.msg {
  padding: 8px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
}

.msg-error {
  background: var(--danger-soft);
  border: 1px solid rgba(239, 68, 68, 0.15);
  color: #fca5a5;
}

.msg-ok {
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.15);
  color: #6ee7b7;
}

/* --- Buttons --- */
.save-btn {
  justify-self: start;
  padding: 10px 24px;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.save-btn:hover { opacity: 0.88; transform: translateY(-1px); }

.btn-ghost {
  padding: 10px 20px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-muted);
  font-size: 14px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-ghost:hover { background: rgba(255, 255, 255, 0.03); border-color: var(--border-hover); }

.add-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 18px;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: var(--radius-lg);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.add-btn:hover { opacity: 0.88; transform: translateY(-1px); }
.add-btn svg { width: 16px; height: 16px; }

/* --- User cards --- */
.user-cards {
  display: grid;
  gap: var(--space-3);
}

.user-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: var(--surface);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.user-card:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.user-card-main {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.uc-avatar {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, #334155, #475569);
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 16px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.uc-avatar.admin {
  background: linear-gradient(135deg, var(--accent), #0891b2);
  color: #fff;
}

.uc-info { display: grid; gap: 2px; }

.uc-name {
  font-weight: 600;
  font-size: 15px;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.uc-meta {
  font-size: 12px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 4px;
}

.uc-dot { opacity: 0.4; }

.uc-actions {
  display: flex;
  gap: 4px;
}

.act-btn {
  width: 36px;
  height: 36px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg);
  color: var(--text-muted);
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: all var(--transition-fast);
}

.act-btn svg { width: 16px; height: 16px; }
.act-btn:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }
.act-btn.warn:hover { border-color: #f59e0b; color: #f59e0b; background: rgba(245,158,11,0.08); }
.act-btn.danger:hover { border-color: #ef4444; color: #ef4444; background: rgba(239,68,68,0.08); }

.empty-state {
  text-align: center;
  padding: var(--space-10);
  color: var(--text-muted);
  font-size: 14px;
}

/* --- Modal --- */
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-overlay-enter-active,
.modal-overlay-leave-active {
  transition: opacity var(--transition-normal);
}

.modal-overlay-enter-from,
.modal-overlay-leave-to {
  opacity: 0;
}

.modal-card-enter-active,
.modal-card-leave-active {
  transition: all var(--transition-normal);
}

.modal-card-enter-from,
.modal-card-leave-to {
  opacity: 0;
  transform: translateY(16px) scale(0.96);
}

.modal {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: var(--space-6);
  width: 400px;
  box-shadow: var(--shadow-xl);
}

.modal h3 {
  margin: 0 0 4px;
  font-size: 18px;
  color: var(--text);
}

.modal-desc {
  margin: 0 0 var(--space-5);
  color: var(--text-muted);
  font-size: 14px;
}

.modal-desc strong { color: var(--text); }

.modal .field { margin-bottom: var(--space-3); }

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-5);
}

/* --- Mobile responsive --- */
@media (max-width: 640px) {
  .password-form {
    max-width: none;
  }

  .user-card {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-3);
  }

  .uc-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .act-btn {
    width: 40px;
    height: 40px;
  }

  .modal {
    width: calc(100% - 32px);
    max-width: none;
  }
}
</style>
