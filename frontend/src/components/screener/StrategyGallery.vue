<script setup>
import { computed, ref } from "vue";
import StatusBadge from "../ui/StatusBadge.vue";

const props = defineProps({
  strategies: { type: Array, default: () => [] },
  activeId: { type: [Number, null], default: null },
});
const emit = defineEmits(["select"]);

const categories = computed(() => {
  const set = new Set(props.strategies.map((s) => s.category || "其他"));
  return ["全部", ...Array.from(set)];
});
const activeCat = ref("全部");
const filtered = computed(() => {
  if (activeCat.value === "全部") return props.strategies;
  return props.strategies.filter((s) => (s.category || "其他") === activeCat.value);
});
// 分组保留顺序
const grouped = computed(() => {
  const map = new Map();
  for (const s of filtered.value) {
    const cat = s.category || "其他";
    if (!map.has(cat)) map.set(cat, []);
    map.get(cat).push(s);
  }
  return Array.from(map.entries());
});

const MODE_LABEL = { all: "全满足", any: "任一", score: "评分" };

function hitTone(s) {
  if (!s.hit_5d?.length) return "neutral";
  const total = s.total_5d || 0;
  if (total > 0) return "success";
  return "warning";
}
function hitText(s) {
  if (!s.hit_5d?.length) return "近5日 0";
  return `近5日 ${s.total_5d} · 均${s.avg_5d}`;
}
</script>

<template>
  <div class="gallery">
    <div class="cat-bar">
      <button
        v-for="c in categories"
        :key="c"
        class="cat-pill"
        :class="{ active: activeCat === c }"
        type="button"
        @click="activeCat = c"
      >{{ c }}</button>
    </div>

    <div v-for="[cat, items] in grouped" :key="cat" class="cat-group">
      <div class="cat-title">{{ cat }}</div>
      <div
        v-for="s in items"
        :key="s.id"
        class="strat-card"
        :class="{ active: activeId === s.id }"
        @click="emit('select', s)"
      >
        <div class="sc-head">
          <span class="sc-name">{{ s.name }}</span>
          <StatusBadge :status="hitTone(s)" size="sm">{{ hitText(s) }}</StatusBadge>
        </div>
        <p class="sc-desc">{{ s.description || "（无说明）" }}</p>
        <div class="sc-foot">
          <span class="sc-mode" :data-mode="s.match_mode">{{ MODE_LABEL[s.match_mode] || s.match_mode }}</span>
          <span v-if="s.match_mode === 'score' && s.min_score" class="sc-minscore">≥{{ s.min_score }}分</span>
          <span class="sc-conds">{{ s.conditions?.length || 0 }} 条</span>
          <span v-if="!s.is_builtin" class="sc-custom">自定义</span>
        </div>
      </div>
    </div>
    <p v-if="!filtered.length" class="empty-hint">该分类暂无策略</p>
  </div>
</template>

<style scoped>
.gallery { display: flex; flex-direction: column; gap: 14px; }
.cat-bar { display: flex; flex-wrap: wrap; gap: 6px; }
.cat-pill {
  font: inherit; font-size: 12px; cursor: pointer;
  padding: 4px 12px; border-radius: 999px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border, rgba(255, 255, 255, 0.1));
  color: var(--text-muted, #94a3b8);
}
.cat-pill:hover { color: var(--text, #e2e8f0); }
.cat-pill.active {
  background: rgba(6, 182, 212, 0.12);
  border-color: var(--accent, #06b6d4);
  color: var(--accent, #06b6d4);
}

.cat-group { display: flex; flex-direction: column; gap: 8px; }
.cat-title {
  font-size: 11px; font-weight: 600; color: var(--text-muted, #64748b);
  text-transform: uppercase; letter-spacing: 0.06em; padding: 0 2px;
}

.strat-card {
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.strat-card:hover { border-color: rgba(6, 182, 212, 0.4); background: rgba(255, 255, 255, 0.04); }
.strat-card.active {
  border-color: var(--accent, #06b6d4);
  background: rgba(6, 182, 212, 0.06);
  box-shadow: 0 0 0 1px var(--accent, #06b6d4) inset;
}
.sc-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 4px; }
.sc-name { font-weight: 600; color: var(--text, #e2e8f0); font-size: 14px; }
.sc-desc { font-size: 12px; color: var(--text-muted, #94a3b8); margin: 0 0 8px; line-height: 1.5; }
.sc-foot { display: flex; gap: 8px; align-items: center; font-size: 11px; color: var(--text-muted, #64748b); flex-wrap: wrap; }
.sc-mode { padding: 1px 7px; border-radius: 4px; background: rgba(148, 163, 184, 0.12); }
.sc-mode[data-mode="score"] { background: rgba(168, 85, 247, 0.15); color: #c084fc; }
.sc-mode[data-mode="any"] { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
.sc-minscore { color: #c084fc; }
.sc-custom { margin-left: auto; padding: 1px 6px; border-radius: 4px; background: rgba(34, 197, 94, 0.12); color: #4ade80; }
.empty-hint { color: var(--text-muted, #64748b); font-size: 13px; padding: 12px; text-align: center; }
</style>
