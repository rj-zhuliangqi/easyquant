import { onBeforeUnmount } from "vue";

/**
 * C3: 集中管理 setTimeout，组件卸载时自动清理，避免泄漏。
 *
 * 用法：
 *   const { later } = useTimerCleanup();
 *   later(() => doSomething(), 3000);
 *
 * 替代各 view 各自维护 `_timers + onBeforeUnmount` 的重复样板。
 */
export function useTimerCleanup() {
  const _timers = [];

  function later(fn, ms) {
    const id = setTimeout(fn, ms);
    _timers.push(id);
    return id;
  }

  function clear(id) {
    clearTimeout(id);
    const idx = _timers.indexOf(id);
    if (idx >= 0) _timers.splice(idx, 1);
  }

  onBeforeUnmount(() => {
    _timers.forEach((id) => clearTimeout(id));
    _timers.length = 0;
  });

  return { later, clear, _timers };
}
