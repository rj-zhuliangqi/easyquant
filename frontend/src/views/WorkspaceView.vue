<script setup>
import { computed, ref } from "vue";
import { useQuery, useQueryClient } from "@tanstack/vue-query";
import QueryState from "../components/QueryState.vue";
import DataPanel from "../components/ui/DataPanel.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import { fetchJson, pageQueryKey } from "../lib/api";
import { formatDateTime } from "../lib/formatters";

defineOptions({ name: "workspace" });

const queryClient = useQueryClient();

const pageQuery = useQuery({
  queryKey: pageQueryKey("workspace"),
  queryFn: () => fetchJson("/api/page/workspace"),
});

const payload = computed(() => pageQuery.data.value?.payload ?? {});
const queryLoading = computed(() => pageQuery.isLoading.value);
const queryFetching = computed(() => pageQuery.isFetching.value);
const queryUpdatedAt = computed(() => formatDateTime(pageQuery.data.value?.updated_at));
const isEmpty = computed(() =>
  !queryLoading.value &&
  !(payload.value.watched_sectors?.length) &&
  !(payload.value.watched_stocks?.length) &&
  !(payload.value.notes?.length),
);

// P4-1: Workspace 增删改交互（之前全只读，依赖 P5-1f upsert）
const actionError = ref("");
const actionInFlight = ref(false);

const newSector = ref({ sector_type: "industry", sector_name: "" });
const newStock = ref({ stock_code: "", stock_name: "", sector_name: "", watch_reason: "" });
const newNote = ref({ subject_type: "sector", subject_key: "", content: "" });

async function refreshWorkspace() {
  await queryClient.invalidateQueries({ queryKey: pageQueryKey("workspace") });
}

async function addSector() {
  const name = newSector.value.sector_name.trim();
  if (!name) {
    actionError.value = "请填写板块名称";
    return;
  }
  actionError.value = "";
  actionInFlight.value = true;
  try {
    await fetchJson("/api/workspace", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        watched_sectors: [
          ...(payload.value.watched_sectors || []),
          { sector_type: newSector.value.sector_type, sector_name: name },
        ],
        watched_stocks: payload.value.watched_stocks || [],
      }),
    });
    newSector.value.sector_name = "";
    await refreshWorkspace();
  } catch (error) {
    actionError.value = `添加板块失败：${error.message || error}`;
  } finally {
    actionInFlight.value = false;
  }
}

async function addStock() {
  const code = newStock.value.stock_code.trim();
  if (!code) {
    actionError.value = "请填写个股代码";
    return;
  }
  actionError.value = "";
  actionInFlight.value = true;
  try {
    await fetchJson("/api/workspace", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        watched_sectors: payload.value.watched_sectors || [],
        watched_stocks: [
          ...(payload.value.watched_stocks || []),
          {
            stock_code: code,
            stock_name: newStock.value.stock_name.trim() || code,
            sector_name: newStock.value.sector_name.trim() || null,
            watch_reason: newStock.value.watch_reason.trim() || null,
          },
        ],
      }),
    });
    newStock.value = { stock_code: "", stock_name: "", sector_name: "", watch_reason: "" };
    await refreshWorkspace();
  } catch (error) {
    actionError.value = `添加个股失败：${error.message || error}`;
  } finally {
    actionInFlight.value = false;
  }
}

async function removeStock(stockCode) {
  actionError.value = "";
  actionInFlight.value = true;
  try {
    await fetchJson("/api/workspace", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        watched_sectors: payload.value.watched_sectors || [],
        watched_stocks: (payload.value.watched_stocks || []).filter((item) => item.stock_code !== stockCode),
      }),
    });
    await refreshWorkspace();
  } catch (error) {
    actionError.value = `删除个股失败：${error.message || error}`;
  } finally {
    actionInFlight.value = false;
  }
}

async function removeSector(sectorType, sectorName) {
  actionError.value = "";
  actionInFlight.value = true;
  try {
    await fetchJson("/api/workspace", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        watched_sectors: (payload.value.watched_sectors || []).filter(
          (item) => !(item.sector_type === sectorType && item.sector_name === sectorName),
        ),
        watched_stocks: payload.value.watched_stocks || [],
      }),
    });
    await refreshWorkspace();
  } catch (error) {
    actionError.value = `删除板块失败：${error.message || error}`;
  } finally {
    actionInFlight.value = false;
  }
}

async function addNote() {
  const key = newNote.value.subject_key.trim();
  const content = newNote.value.content.trim();
  if (!key || !content) {
    actionError.value = "请填写标的/主题与备注内容";
    return;
  }
  actionError.value = "";
  actionInFlight.value = true;
  try {
    await fetchJson("/api/notes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        subject_type: newNote.value.subject_type,
        subject_key: key,
        content,
      }),
    });
    newNote.value = { subject_type: "sector", subject_key: "", content: "" };
    await refreshWorkspace();
  } catch (error) {
    actionError.value = `添加备注失败：${error.message || error}`;
  } finally {
    actionInFlight.value = false;
  }
}
</script>

<template>
  <section class="page">
    <header class="page-hero">
      <div>
        <p class="eyebrow">观察与备注</p>
        <h2>个人观察台</h2>
        <p class="hero-copy">管理自选股、观察池与笔记，沉淀跨日跟踪的个人标的。</p>
      </div>
      <QueryState :is-loading="queryLoading" :is-fetching="queryFetching" :updated-at="queryUpdatedAt" />
    </header>

    <div v-if="actionError" class="action-error">{{ actionError }}</div>

    <section v-if="isEmpty" class="onboarding-guide">
      <DataPanel title="开始使用观察台">
        <div class="guide-steps">
          <div class="guide-step">
            <span class="step-number">1</span>
            <div>
              <strong>添加观察板块</strong>
              <p>使用下方「添加板块」表单，或前往<RouterLink to="/sector-monitor">板块资金监控</RouterLink>。</p>
            </div>
          </div>
          <div class="guide-step">
            <span class="step-number">2</span>
            <div>
              <strong>添加观察个股</strong>
              <p>使用下方「添加个股」表单，或在机会池中点击关注。</p>
            </div>
          </div>
          <div class="guide-step">
            <span class="step-number">3</span>
            <div>
              <strong>记录交易备注</strong>
              <p>使用下方「添加备注」表单，记录你的交易心得和复盘笔记。</p>
            </div>
          </div>
        </div>
      </DataPanel>
    </section>

    <section class="card-grid three-up">
      <DataPanel title="观察板块">
        <div class="add-row">
          <select v-model="newSector.sector_type" :disabled="actionInFlight">
            <option value="industry">行业</option>
            <option value="concept">概念</option>
          </select>
          <input v-model="newSector.sector_name" placeholder="板块名称" :disabled="actionInFlight" @keyup.enter="addSector" />
          <button class="btn-add" :disabled="actionInFlight" @click="addSector">＋ 添加</button>
        </div>
        <div class="list-stack">
          <div v-for="item in payload.watched_sectors || []" :key="`${item.sector_type}-${item.sector_name}`" class="row-card">
            <strong>{{ item.sector_name }}</strong>
            <small>{{ item.sector_type }}</small>
            <button class="btn-remove" :disabled="actionInFlight" @click="removeSector(item.sector_type, item.sector_name)" title="删除">✕</button>
          </div>
          <EmptyState
            v-if="!(payload.watched_sectors?.length) && !queryLoading"
            title="暂无观察板块"
            description="通过上方表单添加"
          />
        </div>
      </DataPanel>

      <DataPanel title="观察个股">
        <div class="add-row">
          <input v-model="newStock.stock_code" placeholder="代码" class="col-code" :disabled="actionInFlight" />
          <input v-model="newStock.stock_name" placeholder="名称（可选）" class="col-name" :disabled="actionInFlight" />
          <input v-model="newStock.watch_reason" placeholder="观察理由（可选）" class="col-reason" :disabled="actionInFlight" @keyup.enter="addStock" />
          <button class="btn-add" :disabled="actionInFlight" @click="addStock">＋ 添加</button>
        </div>
        <div class="list-stack">
          <div v-for="item in payload.watched_stocks || []" :key="item.stock_code" class="row-card">
            <strong>{{ item.stock_name }}</strong>
            <span>{{ item.stock_code }}</span>
            <small>{{ item.watch_reason || "等待备注" }}</small>
            <button class="btn-remove" :disabled="actionInFlight" @click="removeStock(item.stock_code)" title="删除">✕</button>
          </div>
          <EmptyState
            v-if="!(payload.watched_stocks?.length) && !queryLoading"
            title="暂无观察个股"
            description="通过上方表单添加"
          />
        </div>
      </DataPanel>

      <DataPanel title="备注">
        <div class="add-row">
          <select v-model="newNote.subject_type" :disabled="actionInFlight">
            <option value="sector">板块</option>
            <option value="stock">个股</option>
          </select>
          <input v-model="newNote.subject_key" placeholder="标的/主题" class="col-key" :disabled="actionInFlight" />
          <input v-model="newNote.content" placeholder="备注内容" class="col-content" :disabled="actionInFlight" @keyup.enter="addNote" />
          <button class="btn-add" :disabled="actionInFlight" @click="addNote">＋ 添加</button>
        </div>
        <div class="list-stack">
          <div v-for="item in payload.notes || []" :key="`${item.subject_type}-${item.subject_key}`" class="row-card">
            <strong>{{ item.subject_key }}</strong>
            <small class="row-card-content">{{ item.content }}</small>
          </div>
          <EmptyState
            v-if="!(payload.notes?.length) && !queryLoading"
            title="暂无备注"
            description="通过上方表单添加"
          />
        </div>
      </DataPanel>
    </section>
  </section>
</template>

<style scoped>
.onboarding-guide { margin-bottom: 1.5rem; }
.guide-steps { display: flex; flex-direction: column; gap: 1rem; padding: 0.5rem 0; }
.guide-step { display: flex; gap: 1rem; align-items: flex-start; }
.step-number {
  flex-shrink: 0; width: 2rem; height: 2rem; border-radius: 50%;
  background: rgba(6, 182, 212, 0.15); color: #06b6d4;
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 0.875rem;
}
.guide-step p { margin: 0.25rem 0 0; color: #94a3b8; font-size: 0.875rem; }
.guide-step a { color: #06b6d4; text-decoration: underline; }
.guide-step code {
  background: rgba(148, 163, 184, 0.1); padding: 0.125rem 0.375rem;
  border-radius: 0.25rem; font-size: 0.8rem;
}

/* P4-1: 增删表单 + 行内删除按钮 */
.add-row {
  display: flex; gap: 6px; align-items: center;
  padding: 8px 0 12px; border-bottom: 1px solid var(--border, rgba(148,163,184,0.08));
  margin-bottom: 8px; flex-wrap: wrap;
}
.add-row input, .add-row select {
  background: var(--surface, #1e293b); color: var(--text, #e2e8f0);
  border: 1px solid var(--border, rgba(148,163,184,0.08));
  border-radius: 6px; padding: 6px 8px; font-size: 12px; min-width: 0;
}
.add-row input:focus, .add-row select:focus { outline: none; border-color: rgba(148,163,184,0.25); }
.add-row .col-code { width: 80px; }
.add-row .col-name { width: 110px; }
.add-row .col-reason, .add-row .col-key, .add-row .col-content { flex: 1; min-width: 100px; }
.btn-add {
  padding: 6px 12px; border-radius: 6px; border: none;
  background: var(--accent, #06b6d4); color: #fff;
  font-size: 12px; font-weight: 600; cursor: pointer;
  white-space: nowrap;
}
.btn-add:hover:not(:disabled) { opacity: 0.9; }
.btn-add:disabled { opacity: 0.4; cursor: not-allowed; }

.row-card { position: relative; padding-right: 28px; }
.row-card .btn-remove {
  position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
  width: 22px; height: 22px; padding: 0; border: none;
  background: transparent; color: var(--text-muted, #64748b);
  font-size: 14px; cursor: pointer; border-radius: 4px;
}
.row-card .btn-remove:hover:not(:disabled) { background: rgba(239,68,68,0.15); color: var(--danger, #ef4444); }
.row-card .btn-remove:disabled { opacity: 0.3; cursor: not-allowed; }
.row-card-content { display: block; margin-top: 2px; }

.action-error {
  padding: 8px 12px; margin-bottom: 12px;
  background: var(--danger-soft, rgba(239,68,68,0.1));
  color: var(--danger, #ef4444);
  border-radius: 6px; font-size: 13px;
}
</style>