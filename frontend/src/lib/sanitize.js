import DOMPurify from "dompurify";

/**
 * 消毒 HTML 字符串后再交给 v-html 渲染，防止 AI 产物 / 新闻源内容里的
 * <script>、事件属性（onerror 等）、CSS 注入（style="background:url(...)"
 * 触发 CSS exfil）导致 XSS。
 *
 * 用于：AI 报告（marked 输出 / raw_output HTML）、消息面 raw_output。
 *
 * 配置要点：
 * - `FORBID_TAGS`: style/form/input/iframe/object/embed/textarea/select
 *   （style 标签本身可能藏 @import；这里改用 FORBID_ATTR="style" 即可）
 * - `FORBID_ATTR`: style（防 CSS exfil）+ 事件属性 + srcdoc
 * - `ALLOWED_TAGS`: 白名单收紧，仅保留 AI 报告需要的标记
 */
const SANITIZE_CONFIG = {
  FORBID_TAGS: ["style", "form", "input", "textarea", "select", "iframe", "object", "embed", "link", "meta"],
  FORBID_ATTR: [
    "style",       // CSS 注入（CSS exfil）；颜色改用 class + styles.css
    "onerror",
    "onclick",
    "onload",
    "onmouseover",
    "onfocus",
    "onblur",
    "srcdoc",
  ],
  ALLOWED_TAGS: [
    // 文本结构
    "p", "br", "div", "span", "blockquote",
    // 标题
    "h1", "h2", "h3", "h4", "h5", "h6",
    // 列表
    "ul", "ol", "li",
    // 行内强调
    "strong", "em", "b", "i", "u", "s", "code", "mark", "small", "sub", "sup",
    // 代码
    "pre",
    // 表格
    "table", "thead", "tbody", "tr", "th", "td",
    // 链接（href 走默认 url 校验）
    "a",
    // 图片（src 默认相对路径受限但为安全起见允许）
    "img",
    // 分隔
    "hr",
  ],
};

export function sanitizeHtml(html) {
  return DOMPurify.sanitize(html ?? "", SANITIZE_CONFIG);
}
