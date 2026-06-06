<script setup>
import { computed } from "vue";
import { useQuery } from "@tanstack/vue-query";
import QueryState from "../components/QueryState.vue";
import MetricCard from "../components/ui/MetricCard.vue";
import DataPanel from "../components/ui/DataPanel.vue";
import EmptyState from "../components/ui/EmptyState.vue";
import { fetchJson, pageQueryKey } from "../lib/api";
import { formatDateTime } from "../lib/formatters";

defineOptions({ name: "ai-center" });

const pageQuery = useQuery({
  queryKey: pageQueryKey("ai-center"),
  queryFn: () => fetchJson("/api/page/ai-center"),
});

const payload = computed(() => pageQuery.data.value?.payload ?? {});
const summary = computed(() => payload.value.overview?.summary || {});
const queryLoading = computed(() => pageQuery.isLoading.value);
const queryFetching = computed(() => pageQuery.isFetching.value);
</script>

<template>
  <section class="page">
    <header class="page-hero">
      <div>
        <p class="eyebrow">策略与运行</p>
        <h2>AI 中台</h2>
        <p class="hero-copy">首屏聚合当天概览、任务、运行、规则与回测。</p>
      </div>
      <QueryState :is-loading="queryLoading" :is-fetching="queryFetching" />
    </header>

    <section class="card-grid">
      <MetricCard
        label="当日推荐"
        :value="summary.today_pick_count ?? 0"
        :loading="queryLoading"
        trend="up"
      />
      <MetricCard
        label="昨日跟踪"
        :value="summary.yesterday_followup_count ?? 0"
        :loading="queryLoading"
      />
      <MetricCard
        label="经验条目"
        :value="summary.experience_count ?? 0"
        :loading="queryLoading"
      />
      <MetricCard
        label="成功任务"
        :value="`${summary.ops_summary?.success_jobs ?? 0}/${summary.ops_summary?.total_jobs ?? 0}`"
        :loading="queryLoading"
        :trend="(summary.ops_summary?.success_jobs || 0) >= (summary.ops_summary?.total_jobs || 0) * 0.8 ? 'up' : 'neutral'"
      />
    </section>

    <section class="card-grid two-up">
      <DataPanel title="任务列表">
        <div class="list-stack">
          <div v-for="item in payload.jobs?.items || []" :key="item.id" class="row-card">
            <strong>{{ item.name }}</strong>
            <span>{{ item.display_group }}</span>
            <small>{{ item.latest_run_summary?.status || "未运行" }}</small>
          </div>
          <EmptyState
            v-if="!(payload.jobs?.items?.length) && !queryLoading"
            title="暂无任务"
            description="当前没有配置的任务"
          />
        </div>
      </DataPanel>

      <DataPanel title="最近运行">
        <div class="list-stack">
          <div v-for="item in payload.runs?.items || []" :key="item.id" class="row-card">
            <strong>{{ item.job_name || "未命名任务" }}</strong>
            <span>{{ item.run_type }}</span>
            <small>{{ item.status }}</small>
          </div>
          <EmptyState
            v-if="!(payload.runs?.items?.length) && !queryLoading"
            title="暂无运行记录"
            description="当前没有运行记录"
          />
        </div>
      </DataPanel>
    </section>
  </section>
</template>
