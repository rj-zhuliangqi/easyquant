import { ref, onMounted, onUnmounted } from "vue";

const breakpoints = {
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  "2xl": 1536,
};

export function useResponsive() {
  const width = ref(window.innerWidth);
  const height = ref(window.innerHeight);

  const isMobile = computed(() => width.value < breakpoints.md);
  const isTablet = computed(() => width.value >= breakpoints.md && width.value < breakpoints.lg);
  const isDesktop = computed(() => width.value >= breakpoints.lg);
  const isWide = computed(() => width.value >= breakpoints.xl);

  const isSm = computed(() => width.value >= breakpoints.sm);
  const isMd = computed(() => width.value >= breakpoints.md);
  const isLg = computed(() => width.value >= breakpoints.lg);
  const isXl = computed(() => width.value >= breakpoints.xl);
  const is2xl = computed(() => width.value >= breakpoints["2xl"]);

  function onResize() {
    width.value = window.innerWidth;
    height.value = window.innerHeight;
  }

  onMounted(() => {
    window.addEventListener("resize", onResize);
  });

  onUnmounted(() => {
    window.removeEventListener("resize", onResize);
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
    breakpoints,
  };
}
