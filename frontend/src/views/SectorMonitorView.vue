<script setup>
import { computed, ref, watch } from "vue";
import { useQuery, useMutation, useQueryClient } from "@tanstack/vue-query";
import EChartPanel from "../components/EChartPanel.vue";
import QueryState from "../components/QueryState.vue";
import DataPanel from "../components/ui/DataPanel.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import { fetchJson, pageQueryKey } from "../lib/api";
import { formatAmount, formatDateTime, formatPercent } from "../lib/formatters";

defineOptions({ name: "sector-monitor" });

const queryClient = useQueryClient();
const bootstrapQuery = useQuery({
  queryKey: pageQueryKey("sector-monitor"),
  queryFn: () => fetchJson("/api/page/sector-monitor"),
});

const payload = computed(() => bootstrapQuery.data.value?.payload ?? {});
const selectedSector = ref("");
const selectedGroupId = ref(null);
const showGroupManager = ref(false);
const showAddSectorModal = ref(false);
const newGroupName = ref("");
const newGroupDesc = ref("");
const newGroupType = ref("mixed");
const selectedSectorType = ref("industry");
const selectedSectorName = ref("");
// 趋势图模式：watched = 只显示关注组, default = 显示默认强势流入
const chartMode = ref("default");

// Watch for default selected sector from payload
watch(
  () => payload.value.defaults?.selected_sector,
  (value) => {
    if (value && !selectedSector.value) selectedSector.value = value;
  },
  { immediate: true },
);

// Groups query
const groupsQuery = useQuery({
  queryKey: ["sector-monitor-groups"],
  queryFn: () => fetchJson("/api/sector-monitor/groups"),
  enabled: computed(() => true),
});

const groups = computed(() => groupsQuery.data.value?.groups ?? []);

// Selected group items
const groupItemsQuery = useQuery({
  queryKey: computed(() => ["sector-monitor-group-items", selectedGroupId.value]),
  queryFn: () => fetchJson(`/api/sector-monitor/groups/${selectedGroupId.value}/items`),
  enabled: computed(() => selectedGroupId.value !== null),
});

const groupItems = computed(() => groupItemsQuery.data.value?.items ?? []);

// Watch for first group selection
watch(
  () => groups.value,
  (newGroups) => {
    if (newGroups.length > 0 && selectedGroupId.value === null) {
      selectedGroupId.value = newGroups[0].id;
    }
  },
  { immediate: true },
);

// Workspace query for selected sector
const workspaceQuery = useQuery({
  queryKey: computed(() => ["sector-workspace", selectedSector.value]),
  queryFn: () =>
    fetchJson(
      `/api/sector-workspace?sector_type=industry&sector_name=${encodeURIComponent(selectedSector.value)}&metric=net_strength&granularity=minute&lookback_days=1`,
    ),
  enabled: computed(() => Boolean(selectedSector.value)),
  initialData: () => payload.value.workspace,
  placeholderData: (previous) => previous,
});

// Split group items by sector_type
const industryItems = computed(() => groupItems.value.filter((item) => item.sector_type === "industry"));
const conceptItems = computed(() => groupItems.value.filter((item) => item.sector_type === "concept"));

// Comparison chart data
// When chartMode is "watched" and a group is selected: fetch all items in the group
// When chartMode is "default": use default leaders from payload
const watchedIndustryNames = computed(() => industryItems.value.map((item) => item.sector_name));
const watchedConceptNames = computed(() => conceptItems.value.map((item) => item.sector_name));

// Fetch industry comparison for watched sectors
const industryComparisonQuery = useQuery({
  queryKey: computed(() => ["sector-comparison-industry", watchedIndustryNames.value.join(",")]),
  queryFn: () => {
    const sectors = watchedIndustryNames.value;
    if (sectors.length === 0) return { series: [], labels: [] };
    return fetchJson(
      `/api/comparison?sector_type=industry&metric=net_strength&granularity=minute&lookback_days=1&limit=8&rank_view=leaders&include_sectors=${encodeURIComponent(sectors.join(","))}`,
    );
  },
  enabled: computed(() => chartMode.value === "watched" && watchedIndustryNames.value.length > 0),
});

// Fetch concept comparison for watched sectors
const conceptComparisonQuery = useQuery({
  queryKey: computed(() => ["sector-comparison-concept", watchedConceptNames.value.join(",")]),
  queryFn: () => {
    const sectors = watchedConceptNames.value;
    if (sectors.length === 0) return { series: [], labels: [] };
    return fetchJson(
      `/api/comparison?sector_type=concept&metric=net_strength&granularity=minute&lookback_days=1&limit=8&rank_view=leaders&include_sectors=${encodeURIComponent(sectors.join(","))}`,
    );
  },
  enabled: computed(() => chartMode.value === "watched" && watchedConceptNames.value.length > 0),
});

// Merge comparison data from industry + concept
const mergedComparison = computed(() => {
  if (chartMode.value === "default") {
    return {
      labels: payload.value.comparison?.labels || [],
      series: payload.value.comparison?.series || [],
    };
  }

  // Watched mode: merge industry + concept series
  const indLabels = industryComparisonQuery.data.value?.labels || [];
  const conLabels = conceptComparisonQuery.data.value?.labels || [];
  const indSeries = industryComparisonQuery.data.value?.series || [];
  const conSeries = conceptComparisonQuery.data.value?.series || [];

  // Use the longer labels array
  const labels = indLabels.length >= conLabels.length ? indLabels : conLabels;

  // Merge series, adding sector_type info for styling
  const allSeries = [
    ...indSeries.map((s) => ({ ...s, _sector_type: "industry" })),
    ...conSeries.map((s) => ({ ...s, _sector_type: "concept" })),
  ];

  return { labels, series: allSeries };
});

const comparisonOption = computed(() => {
  const { labels, series } = mergedComparison.value;
  const chartColors = ["#06b6d4", "#8b5cf6", "#f59e0b", "#10b981", "#ec4899", "#6366f1", "#ef4444", "#3b82f6"];

  return {
    tooltip: { trigger: "axis" },
    legend: { top: 0, textStyle: { color: "#94a3b8" } },
    grid: { left: 32, right: 24, top: 40, bottom: 32 },
    xAxis: {
      type: "category",
      data: labels,
      boundaryGap: false,
    },
    yAxis: { type: "value", scale: true },
    series: series.map((s, idx) => ({
      name: s.sector_name,
      type: "line",
      smooth: true,
      showSymbol: false,
      areaStyle: { opacity: 0.08 },
      lineStyle: {
        type: s._sector_type === "concept" ? "dashed" : "solid",
        width: s._sector_type === "concept" ? 2 : 2,
      },
      data: (s.points || []).map((point) => point.value),
      color: chartColors[idx % chartColors.length],
    })),
  };
});

// Mutations
const createGroupMutation = useMutation({
  mutationFn: (data) =>
    fetchJson("/api/sector-monitor/groups", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["sector-monitor-groups"] });
    newGroupName.value = "";
    newGroupDesc.value = "";
    showGroupManager.value = false;
  },
});

const deleteGroupMutation = useMutation({
  mutationFn: (groupId) =>
    fetchJson(`/api/sector-monitor/groups/${groupId}`, { method: "DELETE" }),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["sector-monitor-groups"] });
    selectedGroupId.value = null;
  },
});

const addItemMutation = useMutation({
  mutationFn: ({ groupId, data }) =>
    fetchJson(`/api/sector-monitor/groups/${groupId}/items`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["sector-monitor-group-items"] });
    showAddSectorModal.value = false;
    selectedSectorName.value = "";
  },
});

const removeItemMutation = useMutation({
  mutationFn: ({ groupId, itemId }) =>
    fetchJson(`/api/sector-monitor/groups/${groupId}/items/${itemId}`, { method: "DELETE" }),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["sector-monitor-group-items"] });
  },
});

// Actions
function createGroup() {
  if (!newGroupName.value.trim()) return;
  createGroupMutation.mutate({
    name: newGroupName.value.trim(),
    description: newGroupDesc.value.trim() || undefined,
    group_type: newGroupType.value,
  });
}

function deleteGroup(groupId) {
  if (!confirm("确定要删除这个监控组吗？")) return;
  deleteGroupMutation.mutate(groupId);
}

function addSectorToGroup() {
  if (!selectedSectorName.value || !selectedGroupId.value) return;
  addItemMutation.mutate({
    groupId: selectedGroupId.value,
    data: {
      sector_type: selectedSectorType.value,
      sector_name: selectedSectorName.value,
    },
  });
}

function removeSectorFromGroup(itemId) {
  if (!selectedGroupId.value) return;
  removeItemMutation.mutate({ groupId: selectedGroupId.value, itemId });
}

function selectGroup(groupId) {
  selectedGroupId.value = groupId;
}

// Sector catalog for adding
const sectorCatalog = computed(() => payload.value.sector_catalog ?? { industry: [], concept: [] });

const availableSectors = computed(() => {
  const catalog = sectorCatalog.value[selectedSectorType.value] || [];
  const existing = new Set(groupItems.value.map((item) => item.sector_name));
  return catalog.filter((name) => !existing.has(name));
});

// Query states
const queryLoading = computed(() => bootstrapQuery.isLoading.value);
const queryFetching = computed(() => {
  const base = bootstrapQuery.isFetching.value || workspaceQuery.isFetching.value;
  if (chartMode.value === "watched") {
    return base || industryComparisonQuery.isFetching.value || conceptComparisonQuery.isFetching.value;
  }
  return base;
});
const queryUpdatedAt = computed(() => formatDateTime(bootstrapQuery.data.value?.updated_at));

// Selected group info
const selectedGroup = computed(() => groups.value.find((g) => g.id === selectedGroupId.value));

// Chart mode label
const chartModeLabel = computed(() =>
  chartMode.value === "watched" ? "关注组趋势" : "强势流入趋势",
);
</script>

<template>
  <section class="page">
    <header class="page-hero">
      <div>
        <p class="eyebrow">板块跟踪</p>
        <h2>板块资金监控</h2>
        <p class="hero-copy">自定义监控组，分组管理关注的板块和概念，实时对比资金流向。</p>
      </div>
      <QueryState :is-loading="queryLoading" :is-fetching="queryFetching" :updated-at="queryUpdatedAt" />
    </header>

    <!-- Group Management Bar -->
    <DataPanel title="监控组" class="group-panel">
      <template #actions>
        <!-- 趋势图模式切换开关 -->
        <label class="toggle-switch">
          <input type="checkbox" v-model="chartMode" true-value="watched" false-value="default" />
          <span class="toggle-slider"></span>
          <span class="toggle-label">趋势图显示关注组</span>
        </label>
        <button class="ghost-button" @click="showGroupManager = !showGroupManager">
          <span>{{ showGroupManager ? "关闭管理" : "管理组" }}</span>
        </button>
        <button class="ghost-button" @click="showAddSectorModal = true" :disabled="!selectedGroupId">
          <span>+ 添加板块</span>
        </button>
      </template>

      <div class="group-bar">
        <button
          v-for="group in groups"
          :key="group.id"
          class="ghost-button"
          :class="{ active: selectedGroupId === group.id }"
          @click="selectGroup(group.id)"
        >
          <span>{{ group.name }}</span>
          <small class="group-count">{{ group.items?.length || 0 }}</small>
        </button>
        <button v-if="groups.length === 0" class="ghost-button" @click="showGroupManager = true">
          <span>+ 创建首个监控组</span>
        </button>
      </div>

      <!-- Group Manager Panel -->
      <div v-if="showGroupManager" class="group-manager">
        <div class="manager-section">
          <h4>创建新组</h4>
          <div class="form-row">
            <input v-model="newGroupName" placeholder="组名（如：早盘关注）" class="form-input" />
            <input v-model="newGroupDesc" placeholder="描述（可选）" class="form-input" />
            <select v-model="newGroupType" class="form-select">
              <option value="mixed">混合</option>
              <option value="industry">行业</option>
              <option value="concept">概念</option>
            </select>
            <button class="ghost-button active" @click="createGroup" :disabled="!newGroupName.trim()">
              创建
            </button>
          </div>
        </div>
        <div class="manager-section">
          <h4>现有组</h4>
          <div class="group-list">
            <div v-for="group in groups" :key="group.id" class="group-row">
              <div class="group-info">
                <strong>{{ group.name }}</strong>
                <small>{{ group.group_type }} · {{ group.items?.length || 0 }} 个板块</small>
              </div>
              <button class="ghost-button danger" @click="deleteGroup(group.id)">删除</button>
            </div>
            <EmptyState
              v-if="groups.length === 0"
              title="暂无监控组"
              description="点击上方按钮创建你的第一个监控组"
            />
          </div>
        </div>
      </div>
    </DataPanel>

    <!-- Selected Group Sectors + Comparison Chart -->
    <div class="sector-layout">
      <DataPanel :title="selectedGroup ? `${selectedGroup.name} — 关注列表` : '关注列表'" class="sector-list-panel">
        <div class="list-stack compact">
          <!-- Industry items -->
          <div v-if="industryItems.length > 0" class="list-section">
            <div class="section-label">行业</div>
            <div
              v-for="item in industryItems"
              :key="item.id"
              class="list-button compact"
              :class="{ active: selectedSector === item.sector_name }"
              @click="selectedSector = item.sector_name"
            >
              <div class="sector-row">
                <strong>{{ item.sector_name }}</strong>
                <span class="sector-type-chip industry">行业</span>
              </div>
              <button
                class="remove-btn"
                @click.stop="removeSectorFromGroup(item.id)"
                title="从组中移除"
              >
                ×
              </button>
            </div>
          </div>
          <!-- Concept items -->
          <div v-if="conceptItems.length > 0" class="list-section">
            <div class="section-label">概念</div>
            <div
              v-for="item in conceptItems"
              :key="item.id"
              class="list-button compact"
              :class="{ active: selectedSector === item.sector_name }"
              @click="selectedSector = item.sector_name"
            >
              <div class="sector-row">
                <strong>{{ item.sector_name }}</strong>
                <span class="sector-type-chip concept">概念</span>
              </div>
              <button
                class="remove-btn"
                @click.stop="removeSectorFromGroup(item.id)"
                title="从组中移除"
              >
                ×
              </button>
            </div>
          </div>
          <EmptyState
            v-if="groupItems.length === 0 && !queryLoading"
            title="组内暂无板块"
            description="点击右上角「+ 添加板块」添加关注的板块或概念"
          />
        </div>
      </DataPanel>

      <DataPanel :title="`板块对比趋势 — ${chartModeLabel}`" class="hero-chart-panel wide">
        <EChartPanel :option="comparisonOption" />
      </DataPanel>
    </div>

    <!-- Overview Cards -->
    <div class="card-grid three-up">
      <DataPanel title="强势流入">
        <div class="list-stack">
          <button
            v-for="item in payload.overview?.leaders || []"
            :key="item.sector_name"
            class="list-button"
            :class="{ active: selectedSector === item.sector_name }"
            @click="selectedSector = item.sector_name"
          >
            <strong>{{ item.sector_name }}</strong>
            <span>{{ formatAmount(item.net_amount) }}</span>
            <small class="text-success">{{ formatPercent(item.net_strength * 100) }}</small>
          </button>
          <EmptyState
            v-if="!(payload.overview?.leaders?.length) && !queryLoading"
            title="暂无数据"
            description="当前没有强势流入板块"
          />
        </div>
      </DataPanel>

      <DataPanel title="弱势流出">
        <div class="list-stack">
          <div v-for="item in payload.overview?.laggards || []" :key="item.sector_name" class="row-card">
            <strong>{{ item.sector_name }}</strong>
            <span>{{ formatAmount(item.net_amount) }}</span>
            <small class="text-danger">{{ formatPercent(item.net_strength * 100) }}</small>
          </div>
          <EmptyState
            v-if="!(payload.overview?.laggards?.length) && !queryLoading"
            title="暂无数据"
            description="当前没有弱势流出板块"
          />
        </div>
      </DataPanel>

      <DataPanel title="监控信号">
        <div class="list-stack">
          <div v-for="item in payload.signals?.items || []" :key="item.sector_name" class="row-card">
            <strong>{{ item.sector_name }}</strong>
            <span>持续性 {{ item.persistence }}</span>
            <small>加速度 {{ item.acceleration_1 }}</small>
          </div>
          <EmptyState
            v-if="!(payload.signals?.items?.length) && !queryLoading"
            title="暂无信号"
            description="当前没有监控信号"
          />
        </div>
      </DataPanel>
    </div>

    <!-- Sector Detail + Watchlist -->
    <div class="card-grid two-up">
      <DataPanel title="选中板块摘要">
        <div class="detail-block">
          <strong>{{ workspaceQuery.data?.resolved_sector_name || selectedSector || "等待选择" }}</strong>
          <p>{{ workspaceQuery.data?.detail?.summary_text || "当前聚合视图优先保留上次内容，后台刷新明细。" }}</p>
          <small>更新时间 {{ formatDateTime(workspaceQuery.data?.detail_updated_at || workspaceQuery.data?.detail?.captured_at) }}</small>
        </div>
      </DataPanel>

      <DataPanel title="观察池">
        <div class="list-stack">
          <div v-for="item in payload.watchlist?.items || []" :key="`${item.sector_type}-${item.sector_name}`" class="row-card">
            <strong>{{ item.sector_name }}</strong>
            <small>{{ item.sector_type }}</small>
          </div>
          <EmptyState
            v-if="!(payload.watchlist?.items?.length) && !queryLoading"
            title="暂无观察"
            description="观察池为空"
          />
        </div>
      </DataPanel>
    </div>

    <!-- Add Sector Modal -->
    <Transition name="modal">
      <div v-if="showAddSectorModal" class="modal-overlay" @click="showAddSectorModal = false">
        <div class="modal-panel" @click.stop>
          <header class="modal-header">
            <h3>添加板块到「{{ selectedGroup?.name }}」</h3>
            <button class="modal-close" @click="showAddSectorModal = false">×</button>
          </header>
          <div class="modal-body">
            <div class="form-row">
              <label>
                <span>板块类型</span>
                <select v-model="selectedSectorType" class="form-select">
                  <option value="industry">行业</option>
                  <option value="concept">概念</option>
                </select>
              </label>
            </div>
            <div class="form-row">
              <label>
                <span>选择板块</span>
                <select v-model="selectedSectorName" class="form-select">
                  <option value="">请选择...</option>
                  <option v-for="name in availableSectors" :key="name" :value="name">{{ name }}</option>
                </select>
              </label>
            </div>
            <div v-if="availableSectors.length === 0" class="empty-hint">
              该类型下没有可添加的板块（可能已全部添加）
            </div>
          </div>
          <footer class="modal-footer">
            <button class="ghost-button" @click="showAddSectorModal = false">取消</button>
            <button
              class="ghost-button active"
              @click="addSectorToGroup"
              :disabled="!selectedSectorName"
            >
              添加
            </button>
          </footer>
        </div>
      </div>
    </Transition>
  </section>
</template>

<style scoped>
/* Toggle Switch */
.toggle-switch {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  user-select: none;
}

.toggle-switch input {
  display: none;
}

.toggle-slider {
  width: 36px;
  height: 20px;
  background: var(--surface-hover);
  border-radius: var(--radius-full);
  position: relative;
  transition: background var(--transition-fast);
  border: 1px solid var(--border);
}

.toggle-slider::before {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  background: var(--text-muted);
  border-radius: 50%;
  transition: transform var(--transition-fast), background var(--transition-fast);
}

.toggle-switch input:checked + .toggle-slider {
  background: var(--accent-soft);
  border-color: rgba(6, 182, 212, 0.3);
}

.toggle-switch input:checked + .toggle-slider::before {
  transform: translateX(16px);
  background: var(--accent);
}

.toggle-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}

/* Sector Layout - 窄列表 + 宽图表 */
.sector-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: var(--space-4);
  align-items: start;
}

.sector-list-panel {
  min-width: 0;
}

.sector-list-panel :deep(.panel-body) {
  padding: var(--space-3);
}

.sector-list-panel .list-stack {
  max-height: 520px;
}

.sector-list-panel .list-stack.compact {
  gap: 0;
}

.sector-list-panel .list-button.compact {
  padding: var(--space-2) var(--space-3);
  min-height: 36px;
}

/* List Section Labels */
.list-section {
  display: grid;
  gap: 4px;
}

.section-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: var(--space-2) var(--space-3) 2px;
  margin-top: var(--space-1);
}

.list-section:first-child .section-label {
  margin-top: 0;
}

/* Sector Type Chips */
.sector-type-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 500;
}

.sector-type-chip.industry {
  background: var(--accent-soft);
  color: var(--accent);
}

.sector-type-chip.concept {
  background: var(--warning-soft);
  color: var(--warning);
}

/* Group Bar */
.group-bar {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-bottom: var(--space-3);
}

.group-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: var(--radius-full);
  background: var(--surface-hover);
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 600;
  margin-left: var(--space-1);
}

.ghost-button.active .group-count {
  background: rgba(6, 182, 212, 0.2);
  color: var(--accent);
}

/* Group Manager */
.group-manager {
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border);
  display: grid;
  gap: var(--space-5);
}

.manager-section h4 {
  margin: 0 0 var(--space-3);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
}

.form-row {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
  align-items: flex-end;
}

.form-input,
.form-select {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  padding: 10px 14px;
  color: var(--text);
  font-size: 14px;
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  min-height: 44px;
}

.form-input:focus,
.form-select:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.form-input {
  min-width: 200px;
  flex: 1;
}

.form-select {
  min-width: 120px;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  padding-right: 36px;
}

.group-list {
  display: grid;
  gap: var(--space-2);
}

.group-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--surface-hover);
  border: 1px solid var(--border);
}

.group-info {
  display: grid;
  gap: 2px;
}

.group-info strong {
  font-size: 14px;
  font-weight: 600;
}

.group-info small {
  font-size: 12px;
  color: var(--text-muted);
}

.ghost-button.danger {
  color: var(--danger);
  border-color: rgba(239, 68, 68, 0.2);
}

.ghost-button.danger:hover {
  background: var(--danger-soft);
  border-color: rgba(239, 68, 68, 0.3);
}

/* Sector Row in List */
.sector-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex: 1;
}

/* Remove button in list */
.list-button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.remove-btn {
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  font-size: 16px;
  line-height: 1;
  opacity: 0;
  transition: opacity var(--transition-fast), background var(--transition-fast), color var(--transition-fast);
}

.list-button:hover .remove-btn {
  opacity: 1;
}

.remove-btn:hover {
  background: var(--danger-soft);
  color: var(--danger);
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: grid;
  place-items: center;
  z-index: var(--z-modal);
  padding: var(--space-4);
}

.modal-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  width: 100%;
  max-width: 480px;
  max-height: 80vh;
  overflow: hidden;
  display: grid;
  grid-template-rows: auto 1fr auto;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-5) var(--space-5) var(--space-3);
  border-bottom: 1px solid var(--border);
}

.modal-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.modal-close {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: var(--radius-md);
  color: var(--text-muted);
  font-size: 20px;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.modal-close:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.modal-body {
  padding: var(--space-5);
  overflow-y: auto;
  display: grid;
  gap: var(--space-4);
}

.modal-body label {
  display: grid;
  gap: var(--space-2);
}

.modal-body label > span {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-5) var(--space-5);
  border-top: 1px solid var(--border);
}

.empty-hint {
  padding: var(--space-4);
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  background: var(--surface-hover);
  border-radius: var(--radius-md);
}

/* Modal transition */
.modal-enter-active,
.modal-leave-active {
  transition: opacity var(--transition-normal);
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-panel,
.modal-leave-active .modal-panel {
  transition: transform var(--transition-normal), opacity var(--transition-normal);
}

.modal-enter-from .modal-panel,
.modal-leave-to .modal-panel {
  opacity: 0;
  transform: translateY(12px) scale(0.98);
}

/* Chart panel height */
.hero-chart-panel :deep(.chart-panel) {
  height: 520px;
}

.hero-chart-panel.wide :deep(.chart-panel) {
  height: 520px;
}

@media (max-width: 1024px) {
  .sector-layout {
    grid-template-columns: 1fr;
  }

  .sector-list-panel .list-stack {
    max-height: 320px;
  }

  .hero-chart-panel :deep(.chart-panel),
  .hero-chart-panel.wide :deep(.chart-panel) {
    height: 320px;
  }
}

@media (max-width: 640px) {
  .hero-chart-panel :deep(.chart-panel),
  .hero-chart-panel.wide :deep(.chart-panel) {
    height: 280px;
  }

  .form-row {
    flex-direction: column;
    align-items: stretch;
  }

  .form-input,
  .form-select {
    width: 100%;
    min-width: 0;
  }

  .group-bar {
    overflow-x: auto;
    flex-wrap: nowrap;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }

  .group-bar::-webkit-scrollbar {
    display: none;
  }

  .remove-btn {
    opacity: 1;
  }

  .toggle-switch {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
