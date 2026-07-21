import { ref, computed, onMounted, onUnmounted } from "vue";

const breakpoints = {
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  "2xl": 1536,
};

export function useResponsive() {
  const width = ref(typeof window !== "undefined" ? window.innerWidth : 1024);
  const height = ref(typeof window !== "undefined" ? window.innerHeight : 768);

  let rafId = null;

  function onResize() {
    if (rafId) return;
    rafId = requestAnimationFrame(() => {
      width.value = window.innerWidth;
      height.value = window.innerHeight;
      rafId = null;
    });
  }

  onMounted(() => {
    window.addEventListener("resize", onResize, { passive: true });
  });

  onUnmounted(() => {
    window.removeEventListener("resize", onResize);
    if (rafId) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  });

  const isMobile = computed(() => width.value < breakpoints.md);
  const isTablet = computed(() => width.value >= breakpoints.md && width.value < breakpoints.lg);
  const isDesktop = computed(() => width.value >= breakpoints.lg);
  const isWide = computed(() => width.value >= breakpoints.xl);

  const isSm = computed(() => width.value >= breakpoints.sm);
  const isMd = computed(() => width.value >= breakpoints.md);
  const isLg = computed(() => width.value >= breakpoints.lg);
  const isXl = computed(() => width.value >= breakpoints.xl);
  const is2xl = computed(() => width.value >= breakpoints["2xl"]);

  // Used by components for layout decisions (e.g., list-detail vs stacked)
  const isMobileLayout = computed(() => width.value < breakpoints.md);

  // Current breakpoint name
  const currentBreakpoint = computed(() => {
    if (width.value >= breakpoints["2xl"]) return "2xl";
    if (width.value >= breakpoints.xl) return "xl";
    if (width.value >= breakpoints.lg) return "lg";
    if (width.value >= breakpoints.md) return "md";
    if (width.value >= breakpoints.sm) return "sm";
    return "xs";
  });

  return {
    width,
    height,
    isMobile,
    isTablet,
    isDesktop,
    isWide,
    isSm,
    isMd,
    isLg,
    isXl,
    is2xl,
    isMobileLayout,
    currentBreakpoint,
    breakpoints,
  };
}
