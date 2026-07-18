<script setup>
import { computed } from "vue";
import { useQuery } from "@tanstack/vue-query";
import QueryState from "../components/QueryState.vue";
import DataPanel from "../components/ui/DataPanel.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import { fetchJson, pageQueryKey } from "../lib/api";
import { formatDateTime } from "../lib/formatters";

defineOptions({ name: "workspace" });

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

    <section v-if="isEmpty" class="onboarding-guide">
      <DataPanel title="开始使用观察台">
        <div class="guide-steps">
          <div class="guide-step">
            <span class="step-number">1</span>
            <div>
              <strong>添加观察板块</strong>
              <p>前往<RouterLink to="/sector-monitor">板块资金监控</RouterLink>，在自选编辑区将板块加入观察池</p>
            </div>
          </div>
          <div class="guide-step">
            <span class="step-number">2</span>
            <div>
              <strong>添加观察个股</strong>
              <p>在机会池中点击关注，或通过 API 添加个股到观察列表</p>
            </div>
          </div>
          <div class="guide-step">
            <span class="step-number">3</span>
            <div>
              <strong>记录交易备注</strong>
              <p>通过 API <code>POST /api/notes</code> 添加你的交易心得和复盘笔记</p>
            </div>
          </div>
        </div>
      </DataPanel>
    </section>

    <section class="card-grid three-up">
      <DataPanel title="观察板块">
        <div class="list-stack">
          <div v-for="item in payload.watched_sectors || []" :key="`${item.sector_type}-${item.sector_name}`" class="row-card">
            <strong>{{ item.sector_name }}</strong>
            <small>{{ item.sector_type }}</small>
          </div>
          <EmptyState
            v-if="!(payload.watched_sectors?.length) && !queryLoading"
            title="暂无观察板块"
            description="在板块监控中添加观察"
          />
        </div>
      </DataPanel>

      <DataPanel title="观察个股">
        <div class="list-stack">
          <div v-for="item in payload.watched_stocks || []" :key="item.stock_code" class="row-card">
            <strong>{{ item.stock_name }}</strong>
            <span>{{ item.stock_code }}</span>
            <small>{{ item.watch_reason || "等待备注" }}</small>
          </div>
          <EmptyState
            v-if="!(payload.watched_stocks?.length) && !queryLoading"
            title="暂无观察个股"
            description="添加个股到观察列表"
          />
        </div>
      </DataPanel>

      <DataPanel title="备注">
        <div class="list-stack">
          <div v-for="item in payload.notes || []" :key="`${item.subject_type}-${item.subject_key}`" class="row-card">
            <strong>{{ item.subject_key }}</strong>
            <small>{{ item.content }}</small>
          </div>
          <EmptyState
            v-if="!(payload.notes?.length) && !queryLoading"
            title="暂无备注"
            description="添加你的交易备注"
          />
        </div>
      </DataPanel>
    </section>
  </section>
</template>

<style scoped>
.onboarding-guide {
  margin-bottom: 1.5rem;
}

.guide-steps {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 0.5rem 0;
}

.guide-step {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}

.step-number {
  flex-shrink: 0;
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  background: rgba(6, 182, 212, 0.15);
  color: #06b6d4;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.875rem;
}

.guide-step p {
  margin: 0.25rem 0 0;
  color: #94a3b8;
  font-size: 0.875rem;
}

.guide-step a {
  color: #06b6d4;
  text-decoration: underline;
}

.guide-step code {
  background: rgba(148, 163, 184, 0.1);
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
  font-size: 0.8rem;
}
</style>
