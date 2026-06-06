<script setup>
import { computed } from "vue";
import { useQuery } from "@tanstack/vue-query";
import QueryState from "../components/QueryState.vue";
import { fetchJson, pageQueryKey } from "../lib/api";

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
      <article class="metric-card">
        <span>当日推荐</span>
        <strong>{{ summary.today_pick_count ?? 0 }}</strong>
      </article>
      <article class="metric-card">
        <span>昨日跟踪</span>
        <strong>{{ summary.yesterday_followup_count ?? 0 }}</strong>
      </article>
      <article class="metric-card">
        <span>经验条目</span>
        <strong>{{ summary.experience_count ?? 0 }}</strong>
      </article>
      <article class="metric-card">
        <span>成功任务</span>
        <strong>{{ summary.ops_summary?.success_jobs ?? 0 }}/{{ summary.ops_summary?.total_jobs ?? 0 }}</strong>
      </article>
    </section>

    <section class="card-grid two-up">
      <article class="panel">
        <div class="panel-head"><h3>任务列表</h3></div>
        <div class="list-stack">
          <div v-for="item in payload.jobs?.items || []" :key="item.id" class="row-card">
            <strong>{{ item.name }}</strong>
            <span>{{ item.display_group }}</span>
            <small>{{ item.latest_run_summary?.status || "未运行" }}</small>
          </div>
        </div>
      </article>
      <article class="panel">
        <div class="panel-head"><h3>最近运行</h3></div>
        <div class="list-stack">
          <div v-for="item in payload.runs?.items || []" :key="item.id" class="row-card">
            <strong>{{ item.job_name || "未命名任务" }}</strong>
            <span>{{ item.run_type }}</span>
            <small>{{ item.status }}</small>
          </div>
        </div>
      </article>
    </section>
  </section>
</template>
