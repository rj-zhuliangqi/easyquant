import { ref, watch } from "vue";

/**
 * C5: 封装"筛选驱动的列表"通用模式（AlertsView / OpportunityPoolView 共用）。
 *
 * 负责：
 * - requestSeq 竞态保护：快速切筛选时旧响应晚到则丢弃
 * - loading / fetching / error 三个状态 ref
 * - watch(filters) 触发 refresh（可选 beforeRefresh 钩子，如重置 selectedIndex）
 *
 * 调用方提供 ``fetcher(isCurrent)``：做实际请求 + 状态赋值，在 await 后用
 * ``isCurrent()`` 判定是否仍为最新请求，否则早返回（与原内联实现语义一致）。
 *
 * @returns {{ loading, fetching, error, refresh }}
 */
export function useFilteredList({ filters, fetcher, beforeRefresh = null }) {
  const loading = ref(true);
  const fetching = ref(false);
  const error = ref(null);
  let requestSeq = 0;

  async function refresh() {
    const seq = ++requestSeq;
    fetching.value = true;
    error.value = null;
    const isCurrent = () => seq === requestSeq;
    try {
      await fetcher(isCurrent);
    } catch (e) {
      if (isCurrent()) error.value = e.message || String(e);
    } finally {
      if (isCurrent()) {
        loading.value = false;
        fetching.value = false;
      }
    }
  }

  if (filters) {
    watch(filters, async () => {
      if (beforeRefresh) beforeRefresh();
      await refresh();
    });
  }

  return { loading, fetching, error, refresh };
}
