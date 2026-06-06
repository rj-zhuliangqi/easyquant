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
</script>

<template>
  <section class="page">
    <header class="page-hero">
      <div>
        <p class="eyebrow">观察与备注</p>
        <h2>个人观察台</h2>
        <p class="hero-copy">将观察池与备注作为一个稳定页面实例保留下来。</p>
      </div>
      <QueryState :is-loading="queryLoading" :is-fetching="queryFetching" :updated-at="queryUpdatedAt" />
    </header>

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
