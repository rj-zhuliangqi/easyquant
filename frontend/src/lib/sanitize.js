import DOMPurify from "dompurify";

/**
 * 消毒 HTML 字符串后再交给 v-html 渲染，防止 AI 产物 / 新闻源内容里的
 * <script>、事件属性（onerror 等）导致 XSS。
 *
 * 用于：AI 报告（marked 输出 / raw_output HTML）、消息面 raw_output。
 * 静态内部 SVG 图标也走此函数以统一入口、便于审计。
 */
const SANITIZE_CONFIG = {
  FORBID_TAGS: ["style", "form", "input", "iframe", "object", "embed"],
  FORBID_ATTR: ["onerror", "onclick", "onload", "srcdoc"],
};

export function sanitizeHtml(html) {
  return DOMPurify.sanitize(html ?? "", SANITIZE_CONFIG);
}
