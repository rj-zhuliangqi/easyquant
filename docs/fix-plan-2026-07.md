# easyquant 修复与优化计划

> 生成日期：2026-07-17
> 依据：对后端（app/）、前端（frontend/src/）、数据层、脚本与仓库卫生的全量代码审查。
> 使用方式：按 P0 → P4 优先级顺序执行；每项包含【问题】【位置】【修复方案】【验收标准】，可单独勾选完成。

---

## 目录

- [P0 安全与数据安全（立即修）](#p0-安全与数据安全立即修)
- [P1 仓库卫生与止血（半天）](#p1-仓库卫生与止血半天)
- [P2 前端 Bug 修复](#p2-前端-bug-修复)
- [P3 前端去冗余与设计统一](#p3-前端去冗余与设计统一)
- [P4 功能补全](#p4-功能补全)
- [P5 后端架构整理](#p5-后端架构整理)

---

# P0 安全与数据安全（立即修）

服务通过 cloudflared 暴露在公网，以下问题都是**正在发生的风险**，优先于一切优化。

## P0-1 认证白名单放行 `/api/page/`，核心数据裸奔

**问题**：未登录即可访问所有页面聚合接口，包括 AI 选股、自选股、笔记、AI 任务配置。

**位置**：`app/dependencies.py:14`

```python
public_paths = ("/api/auth/", "/api/status", "/api/page/")  # ← /api/page/ 必须移除
```

**修复方案**：
1. 从 `public_paths` 中删除 `"/api/page/"`，只保留 `("/api/auth/", "/api/status")`。
2. 前端确认：SPA 首屏数据拉取（`frontend/src/lib/api.js` 的 `fetchJson`）已统一携带 Bearer token，401 时跳登录页——现有逻辑已支持，无需改动；逐个页面过一遍确认没有绕过 `fetchJson` 的裸 `fetch`（重点查 AlertsView、OpportunityPoolView 的手动刷新函数，它们也需要带 token）。

**验收标准**：未登录状态 `curl https://<域名>/api/page/ai-center` 返回 401；登录后各页面数据正常加载。

---

## P0-2 数据库"恢复"逻辑是反复损坏的根因

**问题**：`integrity_check` 抛出的**任何异常**（包括 `database is locked`）都被判定为"数据库损坏"，随后强删 `-wal`/`-shm` 并重建。launchd 托管实例与手动启动实例并存时，B 进程启动撞锁 → 误判损坏 → 删掉 A 进程正在写的 WAL → **真损坏**。实锤：`data/` 下 22 个 `.corrupted.*` 备份共 9.8G，2026-06-23 25 分钟内连环损坏 5 次（与 launchd KeepAlive 重启节奏吻合），恢复日志中有 `database is locked` 失败记录。

**位置**：`app/main.py:98-155` `_recover_sqlite_if_corrupted`

**修复方案**：
1. **异常 ≠ 损坏**：`integrity_check` 只有在**成功执行并返回非 "ok" 结果**时才判定损坏；`OperationalError`（locked 等）只重试（最多 3 次、间隔 2s），重试仍失败则**放弃启动并明确报错**，绝不 rename/删除。
2. **恢复前先备份 WAL/SHM**：将 `-wal`/`-shm` 一并 rename 备份（而不是 unlink 删除），WAL 里可能有 34M 未 checkpoint 的数据。
3. **加排他文件锁**：恢复前用 `fcntl.flock` 对 DB 文件加排他锁，确认无其他进程持有；拿不到锁就报错退出，不恢复。
4. **消除双实例根源**：确认 launchd 与 `start.sh` 只保留一种启动方式（建议保留 launchd，删除/停用 start.sh 的 PID 管理），写进根 `CLAUDE.md`。
5. `synchronous=NORMAL`（`main.py:92-94`）保持 WAL 下可接受，但恢复流程修正前建议临时调回 `FULL` 降低断电损坏概率（可选）。

**验收标准**：
- 单元测试：模拟 `integrity_check` 抛 `OperationalError("database is locked")`，断言 DB 文件未被 rename、WAL 未被删除。
- 双进程场景手工验证：进程 A 运行中时启动进程 B，B 报"数据库被占用"退出，A 不受影响。

---

## P0-3 akshare 超时是假超时，线程会被耗死

**问题**：`future.result(timeout=25)` 超时后，退出 `with ThreadPoolExecutor(...)` 块会执行 `shutdown(wait=True)`，**阻塞到底层 fetcher 真正跑完**。akshare 内部 requests 多数无 timeout，一旦挂起，"25s 超时"实际变成无限等待，scheduler 10 个线程会被逐个耗死，全站数据采集停摆。

**位置**：`app/akshare_client.py:950-959` `_run`

**修复方案**：
```python
def _run(self, fetcher, timeout_seconds: int = 25) -> pd.DataFrame:
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fetcher)
    try:
        result = future.result(timeout=timeout_seconds)
        return result if isinstance(result, pd.DataFrame) else pd.DataFrame()
    except TimeoutError:
        future.cancel()
        logger.warning("akshare fetcher timeout after %ss", timeout_seconds)
        return pd.DataFrame()
    except Exception:
        logger.exception("akshare fetcher failed")
        return pd.DataFrame()
    finally:
        executor.shutdown(wait=False)  # 不等待卡死的线程
```
1. 按上式改造 `_run`（手动管理 executor，`shutdown(wait=False)`）。
2. **底层加显式 timeout**：审查 `_request_get`（`akshare_client.py:694`）及所有 `requests.get/post` 调用点，统一 `timeout=(5, 20)`（连接 5s、读 20s）；对 `ak.xxx()` 原生调用无法传 timeout 的，保持 `_run` 兜底。
3. `_request_get` 裸吞异常处补日志（当前故障完全不可观测）。
4. 附带修 `akshare_client.py:621`：东财分页 `page_size` 硬钳 100 导致拉 10000 条要 54~100 个串行请求——确认东财接口是否接受更大 page_size（实测 200/500），减少请求数。

**验收标准**：单元测试：fetcher 里 `time.sleep(60)`，断言 `_run` 在 ~25s 返回空 DataFrame 且不阻塞。scheduler 日志中能看到 timeout warning。

---

## P0-4 认证实现加固（公网部署，组合风险高）

**问题**：
- `app/config.py:17`：`JWT_SECRET` 默认 `"change-me-in-production"`（23 字节），生产未配环境变量时任何人可伪造 token；PyJWT 已报 `InsecureKeyLengthWarning`。
- `app/services/auth.py:24-29`：密码用 SHA-256+salt，无 KDF，GPU 暴破成本极低。
- `app/services/auth.py:117-122`：自动创建 `admin/admin123`，仅日志警告。
- `app/services/auth.py:38`：摘要比较用 `==`（非恒定时间）。

**位置**：`app/config.py`、`app/services/auth.py`

**修复方案**：
1. **JWT_SECRET**：启动时检查——若仍是默认值，打印醒目警告并**生成随机密钥写入环境/本地配置文件**（或直接拒绝启动，二选一；个人项目建议前者）。要求 ≥32 字节。
2. **密码哈希换 PBKDF2**：用 stdlib `hashlib.pbkdf2_hmac("sha256", password, salt, 600_000)`，存储格式 `pbkdf2$iterations$salt$hash`。验证函数兼容旧格式（检测到旧格式验证通过后自动重存为新格式，实现无感迁移）。比较用 `hmac.compare_digest`。
3. **默认管理员**：`admin/admin123` 创建时强制随机初始密码并打印到启动日志（或标记 `must_change_password`，首次登录强制改密）。
4. 补测试：登录、错误密码、过期 token、改密后旧密码失效。

**验收标准**：默认密钥启动时有明确警告/拒绝；数据库中密码字段为 `pbkdf2$...` 格式；旧密码迁移路径测试通过。

---

## P0-5 AuthMiddleware 在事件循环里做同步 DB 查询

**问题**：`BaseHTTPMiddleware.dispatch` 跑在事件循环上，`session_factory() + resolve_token()` 是同步 SQLite 调用；DB 被写锁占用时 `busy_timeout=30000` 意味着**事件循环最长冻结 30s**——所有请求、SSE 流全部卡死。

**位置**：`app/dependencies.py:23-24`

**修复方案**（二选一，推荐 A）：
- **方案 A（推荐）**：token 校验改为纯 JWT 解码校验（不查库），`is_active` 检查降级为在写操作路由上做一次（或接受 token 7 天有效期内不实时吊销，配合 P0-4 改密后失效机制：改密时更新用户记录里的 `token_version`，JWT 携带 version 声明校验——仍无需查库）。
- **方案 B**：`user = await run_in_threadpool(_resolve, ...)`（`starlette.concurrency.run_in_threadpool`），改动最小。

**验收标准**：压测/手工验证：对一个表加写锁后请求任意 API，事件循环不冻结（其他请求正常响应）。

---

## P0-6 AI 产出 HTML 未消毒直接 v-html（XSS）

**问题**：AI 生成的报告/对话内容直接 `v-html` 渲染，依赖里无 DOMPurify。AI 输出或新闻源内容若含 `<script>`/事件属性（如 `onerror`）即 XSS；JWT token 又存在 localStorage，可被一并窃取——风险链完整。

**位置**：`frontend/src/views/NewsView.vue:320`（raw_output 报告）、`frontend/src/views/AiCenterView.vue:455`（marked 渲染产物）

**修复方案**：
1. `npm install dompurify`。
2. 新建 `frontend/src/lib/sanitize.js`：
```js
import DOMPurify from "dompurify";
export function sanitizeHtml(html) {
  return DOMPurify.sanitize(html ?? "", {
    FORBID_TAGS: ["style", "form", "input", "iframe", "object", "embed"],
    FORBID_ATTR: ["onerror", "onclick", "onload", "srcdoc"],
  });
}
```
3. 所有 `v-html` 绑定改为 `v-html="sanitizeHtml(xxx)"`；全局 grep `v-html` 确保无遗漏。
4. marked 渲染链路：marked 输出 → sanitize → v-html。

**验收标准**：向 AI 报告注入 `<img src=x onerror=alert(1)>` 测试内容，页面渲染为纯文本/图片但不执行脚本；grep 确认所有 v-html 都经过 sanitize。

---

## P0-7 skill-chat SSE 心跳发不出去（cloudflared 524 未真正修复）

**问题**：心跳检查在 `proc.stdout.readline()` **返回之后**才执行；Claude 工具调用常 30~60s 静默，readline 阻塞期间零心跳流出，100s 空闲超时照样触发 524。

**位置**：`app/main.py:450-463`（skill-chat SSE 生成器）

**修复方案**：把阻塞读移到独立线程，主循环用队列超时驱动心跳：
```python
import queue, threading

q: queue.Queue = queue.Queue()
def _reader(proc):
    for line in iter(proc.stdout.readline, b""):
        q.put(line)
    q.put(None)  # EOF
threading.Thread(target=_reader, args=(proc,), daemon=True).start()

while True:
    try:
        line = q.get(timeout=15)
    except queue.Empty:
        yield ": heartbeat\n\n"   # 每 15s 无输出就发心跳
        continue
    if line is None:
        break
    yield format_sse(line)
```
注意：子进程结束后仍需 `proc.wait()` 回收；超时无输出且进程已退出时正常结束流。

**验收标准**：模拟一个 60s 无输出的 skill 对话，抓 SSE 流确认每 15s 有心跳帧；cloudflared 下不再出现 524。

---

## P0-8 测试套件失效：35/45 用例 401

**问题**：6/6 上线 AuthMiddleware 后，`tests/test_api.py` 的 `build_client()` 未注入 token，35 个用例全部 401——**回归能力失效一个多月**，后续改动都在裸奔。

**位置**：`tests/test_api.py:513`（`build_client` / `build_client_and_gateway`）

**修复方案**：
1. 在 `build_client_and_gateway` 里创建 TestClient 后，先 `POST /api/auth/login`（测试库会自动建 admin 账户）拿 token，设置 `client.headers["Authorization"] = f"Bearer {token}"`。
2. 跑全量测试，对仍失败的个别用例（可能有行为变化）逐个修正。
3. 附带：P0-1 移除 `/api/page/` 白名单后，page 相关测试同样需要 token——同一次修掉。

**验收标准**：`.venv/bin/python -m pytest tests/ -q` 全部通过（当前 84 passed + 35 failed → 119 passed）。

---

# P1 仓库卫生与止血（半天）

## P1-1 删除 9.8G 损坏数据库备份

**问题**：`data/` 总 18G，22 个 `sector_fund_monitor.db.corrupted.*` 文件占 9.8G。

**修复方案**：
1. 先确认主库健康：`sqlite3 data/sector_fund_monitor.db "PRAGMA integrity_check;"` 返回 `ok`。
2. 保留最新 1 个 corrupted 文件以防万一（移出 data/ 或直接删），其余删除：`rm data/sector_fund_monitor.db.corrupted.*`。
3. 同批清理：`-shm.backup`、`-wal.backup`、`.manual-backup`、`sector_fund_monitor_recovered.db*`。

**验收标准**：`du -sh data/` 从 18G 降到 ~8G；服务正常启动、数据完整。

---

## P1-2 主库移出 git 跟踪

**问题**：`data/sector_fund_monitor.db`（4.9G 二进制）被 git 跟踪且持续 modified，`.git` 已 896M，是仓库膨胀主因。

**修复方案**：
1. `git rm --cached data/sector_fund_monitor.db`（保留磁盘文件，只移出索引）。
2. 确认 `.gitignore` 已覆盖 `data/*.db`（检查现有规则，补上缺失的）。
3. commit 这次变更。
4. （可选，长期）历史已提交的 4.9G 仍在 git 历史中，如需瘦身用 `git filter-repo` 清理——单独评估，不在本次范围。

**验收标准**：`git status` 不再显示主库 modified；clone 体积不再增长。

---

## P1-3 修 .gitignore 缺口

**问题**（实测 `git check-ignore` 验证）：
- 只忽略 `/tmp_*.py`，不覆盖 `.tmp_*`（点前缀）→ 219 个临时文件裸奔。
- `data/*.db-*` 不匹配 `.db.corrupted.*`（点分隔）。
- `test-results/`（连字符）≠ 实际目录 `test_results/`（下划线），7 个 PNG 被误跟踪。
- 未覆盖：`data/ai_center/*.json`、`data/ai_center/processed/`、`data/ai_center/inbox/_failed/`、`data/experiments/`、根目录 `build_review.py`、`.tx_quote.txt`。

**修复方案**：更新 `.gitignore`：
```gitignore
# 临时文件
.tmp_*
tmp_*

# 数据库及衍生文件
data/*.db
data/*.db-*
data/*.db.corrupted.*
data/*.db.backup
data/*.manual-backup
data/sector_fund_monitor_recovered.db*

# 截图与测试结果
test_results/

# AI 中心运行时产物
data/ai_center/*.json
data/ai_center/processed/
data/ai_center/inbox/_failed/
data/experiments/

# 日志
data/*.log
data/cloudflared*.log
```
对已误跟踪的 `test_results/*.png` 执行 `git rm --cached`。

**验收标准**：`git status --short` 干净（只剩真正需要提交的文件）；`git check-ignore` 验证上述各类文件均被忽略。

---

## P1-4 清理临时文件与一次性脚本

**问题**：
- 根目录 219 个 `.tmp_*` 文件（111 py + 92 json 等，~10MB），零代码引用，是 AI 会话产物，且**仍在每天堆积**。
- `scripts/` 顶层 30 个 `_*` 一次性脚本（`_build_0926_*`、`_st_probe*`、`_validate_*`、`_summary_1900_v1~v3`），全部 untracked。
- `scripts/experiments/`（50 个文件）整个 untracked——上次"归位"commit 只移动没 `git add`。
- 根目录还有 `build_review.py`、`.tx_quote.txt`、`inspect_data.py`、`inspect2.py` 等非 tmp 前缀孤儿。

**修复方案**：
1. 根目录 `.tmp_*`：直接删除（P1-3 的 gitignore 已防止复发）。**注意**：`.tmp_ai_work/` 目录如有进行中的工作先确认再删。
2. `scripts/_*.py`：逐个快速扫一眼，确认无长期价值后移到 `scripts/experiments/`（按根 CLAUDE.md 约定）或删除；`fetch_data.py`、`run_skill.sh`、`generate_panqian_report.py` 保留原位。
3. `git add scripts/experiments/` 补上遗漏的跟踪。
4. 根目录其他孤儿脚本同样移入 `scripts/experiments/` 或删除。

**验收标准**：根目录 `ls .tmp_* 2>/dev/null | wc -l` 为 0；`scripts/` 顶层只剩 3~4 个常驻脚本；`git status` 无大量 untracked。

---

## P1-5 禁止脚本裸连主库 + 修正文档

**问题**：
- `scripts/_st_probe2_2026-06-30.py:10`、`_st_db_inspect.py:2`、`_st_probe4_2026-06-30.py:59` 等用裸 `sqlite3.connect('data/sector_fund_monitor.db')`（无 busy_timeout、无 WAL 协调）直写主库，加剧损坏风险；`app/run_stock_research.py:28` 也另起进程写库。
- 根 `CLAUDE.md` 写"13 个 AI Skill"，实测 `app/ai_center_registry.py:22` 是 **12 个**；目录约定"12 个内置定时任务"自相矛盾。
- 约定"一次性实验脚本放 `scripts/experiments/`"从未执行。
- 5 个 CLAUDE.md（app/、data/、frontend/ 等）是 claude-mem 自动生成的空壳，无实质内容。

**修复方案**：
1. 随 P1-4 删除/归档这些探针脚本；需要保留的 DB 检查脚本改为只读模式：`sqlite3.connect("file:data/sector_fund_monitor.db?mode=ro", uri=True)`。
2. 修正根 `CLAUDE.md`：Skill 数量改 12；明确"启动方式只保留 launchd 一种"（配合 P0-2）；把 P1 系列约定写进去。
3. 删除或重写空壳 CLAUDE.md（有实质内容才保留）。

**验收标准**：grep 确认无裸写主库的脚本残留；CLAUDE.md 与实际代码一致。

---

# P2 前端 Bug 修复

## P2-1 中文输入法回车误发消息（高）

**问题**：聊天输入框 `@keydown.enter.prevent="sendChatMessage"` 未判断 `event.isComposing`，中文拼音选词按回车会直接把半成品消息发出去；且 `.prevent` 使换行彻底不可能。

**位置**：`frontend/src/views/AiCenterView.vue:549`

**修复方案**：
```vue
<textarea
  @keydown.enter.exact="onEnterSend"
  @keydown.shift.enter.exact.prevent="insertNewline"
/>
```
```js
function onEnterSend(e) {
  if (e.isComposing) return;   // IME 组词中不发送
  e.preventDefault();
  sendChatMessage();
}
```
Enter 发送、Shift+Enter 换行；并在输入框下方加一行小字提示"Enter 发送，Shift+Enter 换行"。

**验收标准**：中文输入法选词回车不发送；Enter 发送；Shift+Enter 换行。

---

## P2-2 全站零错误态 UI，故障与无数据不可区分（高）

**问题**：全项目 grep 不到一个 `isError` 使用。`/api/page/*` 失败后指标卡显示 0/"--"、列表显示「暂无数据」——接口故障和真没数据长得一样。AlertsView:38-53、OpportunityPoolView.vue:46-60 的手动刷新连 `catch` 都没有（只有 `finally`），失败即 unhandled rejection + 静默保留旧数据。

**位置**：全部 view；重点 `AlertsView.vue`、`OpportunityPoolView.vue`、`components/QueryState.vue`

**修复方案**：
1. 扩展 `QueryState.vue` 支持 error 态：新增 `error` prop（或读 vue-query 的 `isError`/`error`），显示「加载失败 + 重试按钮」（重试调 `refetch()`）。
2. 每个页面的 `useQuery` 结果解构出 `isError`，传给 QueryState；失败时列表区显示错误态而非「暂无数据」。
3. 手动刷新函数补 `try/catch`：catch 里设置本地 `loadError` ref 并在 UI 展示「刷新失败，数据为 X 分钟前」提示。
4. 指标卡在错误态显示 `--` 并标灰，而不是显示 0。

**验收标准**：断开后端后逐页检查，每页显示明确的错误提示和重试入口；无 unhandled rejection（console 干净）。

---

## P2-3 StatusBadge 不响应 props 变化（高）

**问题**：`config` 在 setup 顶层用 `props.status` 计算（非 computed），状态切换后文字变了颜色不变。

**位置**：`frontend/src/components/ui/StatusBadge.vue:21-22`（影响 UserMgmtView）

**修复方案**：
```js
const config = computed(() => STATUS_MAP[props.status] ?? DEFAULT_CONFIG);
```
模板中 `config.xxx` 引用不变（computed 自动解包）。

**验收标准**：UserMgmtView 切换用户 active 状态，徽标颜色即时跟随变化。

---

## P2-4 AiJobsView 时钟冻结（高）

**问题**：`queryUpdatedAt`（:56）和 `nowMinutes`（:63-66）都是**无响应式依赖的 computed**——只算一次。keep-alive 页面下"更新于"永远显示首次挂载时间；`deriveState`（:75-87）的 past-due 判断用的也是挂载时刻分钟数，30s 轮询刷新数据但状态推导永不前进。

**位置**：`frontend/src/views/AiJobsView.vue:56,63-66,75-87`

**修复方案**：
1. `queryUpdatedAt` 改为直接使用 vue-query 的 `dataUpdatedAt`（响应式）：`const updatedAt = computed(() => new Date(query.dataUpdatedAt.value))`。
2. `nowMinutes` 改为跟随 `dataUpdatedAt` 重算：`const nowMinutes = computed(() => { void query.dataUpdatedAt.value; const d = new Date(); return d.getHours() * 60 + d.getMinutes(); })`——这样每次数据刷新（30s）状态推导都会前进；如需更高频，再加一个 60s 的 `setInterval` 驱动 `now` ref（组件失活时清除）。

**验收标准**：打开 AiJobs 页等 2 分钟，"更新于"时间随轮询前进；一个到点的任务在轮询后状态从"等待中"变为"已逾期"。

---

## P2-5 筛选竞态：旧条件响应覆盖新条件数据

**问题**：快速连切筛选时多个 `refreshAlerts/refreshOpportunities` 并发，无取消/序号保护，后到的旧条件响应覆盖新条件数据。

**位置**：`frontend/src/views/AlertsView.vue:63-66`、`frontend/src/views/OpportunityPoolView.vue:70-73`

**修复方案**（二选一）：
- 序号保护（简单）：
```js
let requestSeq = 0;
async function refreshAlerts() {
  const seq = ++requestSeq;
  try {
    const data = await fetchJson(url);
    if (seq !== requestSeq) return;  // 已有更新的请求
    alerts.value = data;
  } catch (e) { if (seq === requestSeq) loadError.value = e; }
}
```
- 或 AbortController 取消上一个请求。
- 长期方案：这两个页面迁回 `useQuery`（queryKey 含筛选条件），vue-query 天然处理竞态——推荐在 P3 做。

**验收标准**：快速切换筛选 5 次，最终展示数据与最终选中的筛选条件一致。

---

## P2-6 RealtimeFeed 分页游标错误

**问题**：`loadMore` 用**本地重排后**列表最后一项的 id 当 `since_id`；sort=important/hot/mixed 时最后一项不是最旧条目，导致翻漏或翻重。

**位置**：`frontend/src/components/news/RealtimeFeed.vue:132-151`

**修复方案**：分页游标必须基于**服务端排序键**（时间/id），与本地展示排序解耦：
1. 维护独立 `oldestId` ref：每次接口返回后，取**返回数据原始顺序**的最后一项 id 更新（不要用本地排序后的列表）。
2. 本地排序只影响展示，不影响游标。

**验收标准**：sort=important 模式下连续 loadMore 3 页，无重复、无遗漏（对比接口原始数据）。

---

## P2-7 缓存预热时区不一致，预热白做

**问题**：AppSidebar 预取用 UTC 当天拼 queryKey（AppSidebar.vue:72,81），NewsView/ReviewView 用本地时区拼 key（NewsView.vue:46-61、ReviewView.vue:16-39）——北京时间 0:00-8:00 之间 key 对不上，预热完全失效。AiCenterView.vue:139 的 results 默认日期同样是 UTC。

**位置**：`frontend/src/components/AppSidebar.vue:72-86`、`NewsView.vue:46-52`、`ReviewView.vue:16-19`、`AiCenterView.vue:138-140`、`AiJobsView.vue:58-61`

**修复方案**：统一抽取 `frontend/src/lib/dates.js`：
```js
/** 返回本地时区的 YYYY-MM-DD（全站唯一 todayIso 实现） */
export function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
```
全局替换 5 处实现，统一用本地时区（与后端 naive datetime 现状一致；P5 时区统一后再评估）。

**验收标准**：grep 确认全站只有一个 todayIso 实现；模拟北京时间凌晨 2 点，预热 key 与页面 key 一致。

---

## P2-8 其余中低优先级前端 Bug（打包修）

| # | 位置 | 问题 | 修法 |
|---|---|---|---|
| a | `AiCenterView.vue:433,583` | 用了 `.status-badge` 类但 scoped 样式未定义，徽标渲染为裸文本 | 引入 StatusBadge 组件（P3 推全后自然解决），或补样式 |
| b | `AiJobsView.vue:82` | deriveState 对未知状态（skipped/cancelled）兜底返回 "success"，显示「已完成」 | 兜底改为 "unknown" 中性文案 |
| c | `AiJobsView.vue:90,408-409` | 成功边框红、失败边框也是红，**成功失败同色** | 成功改中性/绿色系，配合 P3 涨跌色统一 |
| d | `AlertsView.vue:126` | `trend="warning"` 在 MetricCard trendIcons 中不存在，图标渲染为空 | 改 "neutral" 或给 MetricCard 补 warning 图标 |
| e | `api.js:12,49` | 401 用 `window.location.href` 硬跳转丢 SPA 状态 | 改 `router.push({ name: "login" })`（注意避免 login 页自身循环） |
| f | `api.js:3` 及所有 queryFn | 请求不接 vue-query 的 `{ signal }`，全部不可取消 | `fetchJson(url, { signal })` 透传；queryFn 改 `({ signal }) => fetchJson(url, { signal })` |
| g | `api.js:25` | 对 200 无脑 `response.json()`，非 JSON 200 会抛未处理异常 | 检查 content-type 再 parse |
| h | `AiJobsView.vue:24,31` | keep-alive 后 30s 双查询永久轮询，切走不停 | `refetchInterval` 改函数形式，结合 `document.hidden` 判断；或用 vue-query 的 `enabled` + 路由激活状态 |
| i | `RealtimeFeed.vue:33` | 60s 轮询无 `document.hidden` 检测 | 同上 |
| j | `AiJobsView.vue:172-180`、`UserMgmtView.vue:133` | setTimeout 未在卸载时清理 | onBeforeUnmount/onDeactivated 里 clearTimeout |
| k | `WorkspaceView.vue:47` | `<a href="/sector-monitor">` 整页刷新 | 改 `<RouterLink>` |
| l | `EChartPanel.vue:150-151` | `generateSummary()` 在模板里每次渲染全量重算 | 改 computed |
| m | `EChartPanel.vue:20-23` | `theme` prop 声明后从未使用 | 删除 prop |
| n | `NewsView.vue:157-159` | 空 watch | 删除 |

**验收标准**：逐项过一遍，console 无警告无未处理异常。

---

# P3 前端去冗余与设计统一

> 目标：消除 ~30% 重复代码，让设计系统真正落地，解决"不高级"的观感问题。

## P3-1 统一涨跌配色（A 股工具的正确性问题）

**问题**：红涨绿跌 vs 绿涨红跌全 App 打架：HomeView:130、MetricCard.vue:18-22、SectorMonitorView.vue:92 用西式绿涨；NewsView、AiCenterView、ReviewView、AiJobsView 用 A 股红涨；AiCenterView 内部就自相矛盾（:216 正则染色 +绿-红，同文件 `.markdown-body .up` 却是红）。且 `--up`/`--down` 两个 token 被 5 个文件使用但**从未定义**，全靠回退值。

**修复方案**：
1. 在 `styles.css` token 层明确定义（A 股惯例）：
```css
:root {
  --up: #f43f5e;    /* 涨 = 红 */
  --down: #10b981;  /* 跌 = 绿 */
  --up-soft: rgba(244, 63, 94, 0.12);
  --down-soft: rgba(16, 185, 129, 0.12);
}
```
2. MetricCard 的涨跌着色改为引用 token；grep 全项目 `#4ade80`、`#22c55e`、`text-success` 等用于涨跌幅的地方，逐一核对语义（注意：状态成功色与涨跌色是两套语义，成功保持绿、涨是红——AiJobsView 的"成功红边框"bug 顺手修掉）。
3. 提供 `frontend/src/lib/formatters.js` 里的 `changeClass(value)` 统一返回 `is-up/is-down`，替换各处正则染色。

**验收标准**：逐页截图核对：所有涨跌幅红涨绿跌；成功/失败状态色与涨跌色不再混用。

---

## P3-2 推全设计系统组件，删除双份 CSS

**问题**：`components/ui/` 下 7 个组件是后补的设计系统，但 `PageHero`、`ListPanel`、`LoadingSkeleton` **全项目 0 import**（死代码）；StatusBadge 仅 1 处使用。与此同时各页面手写重复实现：
- 11 个页面各自手写 hero 头（HomeView:66-73、AiJobsView:234-244……）
- `.status-badge` 样式在 AiJobsView:554-558、ReviewView:628-631 逐字重复
- `.empty-state` 在 AiCenterView:695-697、UserMgmtView:541-546 重造（EmptyState 组件就在旁边）
- 侧边栏整套样式 ~150 行逐字重复（styles.css:189-311 vs AppSidebar.vue:201-347）
- `.metric-card`（styles.css:397-437 vs MetricCard.vue:45-111，全局 `.metric-card span` 还会穿透组件）、`.query-state`（styles.css:637-667 vs QueryState.vue:24-83，全局那份是死的）、`.chart-panel`、关键帧 shimmer×3 / fadeInUp×2

**修复方案**（按组件逐个推全，每步都可单独提交）：
1. **PageHero**：检查组件 API 是否够用（title/subtitle/actions slot），不够就补；然后逐页替换 11 处手写 hero，删除对应 scoped CSS。
2. **StatusBadge**：替换 AiJobsView、ReviewView、AiCenterView 的手写徽标（含 P2-8a 的裸文本问题）。
3. **EmptyState**：替换 AiCenterView、UserMgmtView 自造空态。
4. **LoadingSkeleton**：替换裸文本「加载中...」（UserMgmtView:185、AiJobsView:329），统一 4 套加载态为：首屏骨架（LoadingSkeleton）+ 局部刷新（QueryState）两种。
5. **删全局死 CSS**：styles.css 中与组件重复的侧边栏段、`.query-state`、`.metric-card` 段（保留真正全局的工具类）；删除重复关键帧，统一保留一份。
6. 清理过期 token 回退值：grep `var(--surface,`、`var(--text,` 等，删除与实际 token 值不符的回退（`--surface` 实际是 `#151d2e` 不是 `#1e293b`）。

**验收标准**：`grep -r "PageHero\|ListPanel\|LoadingSkeleton" frontend/src` 有真实使用；styles.css 从 939 行降到 ~500 行；视觉无回归（逐页截图对比）。

---

## P3-3 抽公共逻辑：composable + 统一模板模式

**问题**：
- AlertsView:26-74 与 OpportunityPoolView:22-81 的「bootstrap query + 本地 ref + watch 筛选 + 手动刷新 + 移动端 scrollIntoView」整段近乎逐行相同。
- Tab↔URL query 同步两套：NewsView:16-43 vs AiCenterView:27-66。
- 日期选择器两套：NewsView:197-209 vs ReviewView:124-131，样式还不一致。
- pick 等级文案映射两份且**词汇表冲突**：NewsView:103-112（strong_recommend/recommend/watch/hold）vs AiCenterView:117-120（strong_recommend/confirm/candidate/watch）——先和后端确认真实词汇表。
- 按钮样式约 7 套（.ghost-button/.action-btn/.save-btn/.today-btn/.chat-send-btn……）。

**修复方案**：
1. 新建 `composables/useFilteredList.js`：封装「useQuery + 筛选 ref + 竞态保护 + 错误态」，Alerts/机会池迁入（顺带解决 P2-5）。
2. 新建 `composables/useRouteTab.js`：封装 tab 与 URL query 双向同步，News/AiCenter 迁入。
3. 新建 `components/ui/DateNavigator.vue`：统一日期选择器（前一天/日期/后一天/今天），News/Review 迁入。
4. pick 等级文案收敛到 `lib/formatters.js` 一处（先 `grep` 后端 `app/services/ai_center.py` 确认真实等级枚举）。
5. 新建 `components/ui/AppButton.vue`（或收敛到 2~3 个全局类）：primary/ghost/danger 三变体，逐页替换。
6. 顺带统一两处真相：删除 `router.js:19-28` 无人消费的 meta.keepAlive，以 `App.vue:10` 的 keepAliveNames 为准（或反过来，选一处作为唯一真相），补上漏掉的 "news"。

**验收标准**：Alerts/机会池两页代码量明显下降且行为一致；tab/日期交互两页表现一致；grep 确认 pick 等级文案只有一份。

---

## P3-4 文案与视觉质感

**问题**：
- **Hero 副标题是工程笔记**：HomeView:70「AI 定时任务已移至独立任务页」、SectorMonitorView:71「首屏由聚合接口一次下发……」、LimitUpView:57「切页往返不再重建整个页面」、AlertsView:89「只做局部刷新」、OpportunityPoolView:94「支持切模式时保留旧列表」、WorkspaceView:35「作为一个稳定页面实例保留下来」——这是提交信息，不是产品文案。
- **占位/导流型面板**：Home 的"AI 定时任务"链接卡、AiCenter 配置 tab 的 handoff 卡、概览 tab 四张入口卡（侧边栏已有导航）。
- **图标两套**：侧边栏 SVG 线性图标 vs tab/聊天 emoji（📊📄🤖、👤🤖、"▍" 光标）。
- **MetricCard 假趋势**：HomeView:89,96 硬编码 `trend="up"` 装饰。
- **字体**：index.html:9 从 Google Fonts 加载 Inter/JetBrains Mono，render-blocking 且国内经 cloudflared 可能慢/挂；中文全回落系统字体，混排不统一。
- z-index 硬编码 299/300（App.vue:74、AppSidebar.vue:214）绕过 token。

**修复方案**：
1. 重写所有 hero 副标题为**面向用户的功能描述**（例：板块监控 →「实时追踪行业与概念板块资金流，对比龙头表现」）；移动端隐藏副标题的 CSS（styles.css:853-855）保留。
2. 删除导流/占位卡：Home 的 AI 任务链接卡、AiCenter 概览的四张入口卡——入口交给侧边栏，页面空间留给真实数据（配合 P4-2 概览重做）。
3. 图标统一：tab/聊天 emoji 替换为与侧边栏同风格的 SVG 图标（可抽 `components/ui/AppIcon.vue` 集中管理）；聊天头像 emoji 改首字母/图标块；去掉 "▍" 光标改 CSS 闪烁光标。
4. 假趋势删除或接真实环比数据（首页指标卡如有昨日对比数据就接，没有就不显示 trend）。
5. 字体：将 Inter/JetBrains Mono 自托管（下载 woff2 放 `frontend/public/fonts/`，`@font-face` + `font-display: swap`），或评估后直接移除依赖系统字体栈（中文场景收益不大）——二选一，建议自托管。
6. z-index 收进 token（`--z-sidebar: 300; --z-topbar: 290; --z-modal: 400`），替换硬编码。

**验收标准**：逐页截图评审；Lighthouse 检查字体不再阻塞渲染；无 emoji 图标残留。

---

## P3-5 图表增强与构建优化

**问题**：
- 图表全是单系列折线：无成交量、无 K 线、无 dataZoom，分时图连时间轴格式化都没有（HomeView:35-39 直接用后端 label）。
- 桌面端 `.list-stack` 限高 420px，移动端放开（styles.css:903-906），长列表把详情顶到很靠下靠 scrollIntoView 补救。
- 无代码分割：router.js 全静态 import，echarts+marked 全进首屏 chunk。

**修复方案**：
1. EChartPanel 支持时间轴格式化（按盘中时间 HH:mm 显示），加 `dataZoom`（inside 缩放）配置项（默认关，需要的页面开启）。
2. 首页指数图补成交量副轴（如后端 payload 有量数据；没有则标记依赖后端补充，列入 P4）。
3. 路由懒加载：
```js
const NewsView = () => import("./views/NewsView.vue");
// …全部 view 改动态 import（LoginView 可保持静态）
```
4. `vite.config.js` 加 manualChunks：`echarts` 单独一个 chunk（最大的依赖），`marked`+`dompurify` 一个 chunk。
5. `.list-stack` 限高策略统一：桌面端列表内部滚动，详情面板 sticky——评估后统一实现。

**验收标准**：构建产物首屏 JS 明显下降（对比 build 输出的 chunk 体积）；图表可缩放、时间轴可读。

---

# P4 功能补全

## P4-1 Workspace 补增删改交互（最明显的半成品）

**问题**：三个列表（自选股/观察池/笔记）全只读，空态指引教用户"通过 API POST /api/notes 添加"（WorkspaceView:61）——把没做 UI 写在脸上。且指引提到的"板块监控页的自选编辑区"在 SectorMonitorView 里**根本不存在**。

**修复方案**：
1. 确认后端接口齐全：`grep` 确认 `/api/workspace`、`/api/notes`、watchlist 的 POST/DELETE 端点已存在（报告确认 API 层存在，只缺 UI）。
2. WorkspaceView 补交互：
   - 自选股/观察池：添加（代码+名称搜索或手输）、删除（行内按钮+确认）、排序可选。
   - 笔记：新建/编辑/删除（内联编辑或模态）。
3. 空态文案改为「点击右上角添加」+ 引导按钮。
4. **打通跨页动作**：OpportunityPoolView 详情加「加入观察」按钮（调 watchlist API，已存在则禁用态）；SectorMonitorView 板块行加「观察」切换——兑现现有指引文案的承诺。
5. 注意 P5-5：watchlist 当前全表 delete+insert（workspace.py:69）且无 user_id，交互上线前先修 upsert。

**验收标准**：不碰 API 的情况下完成自选股/笔记的增删改查；从机会池一键加入观察后 Workspace 可见。

---

## P4-2 AiCenter 概览重做 + 「应用此配置」实现或下线

**问题**：
- 概览 tab（AiCenterView:86-115,350-401）= AiJobs+机会池+复盘+消息面的复读 + 侧边栏已有的入口卡，无独有价值。
- Skill 工坊「应用此配置」（:313-318）是**空操作**——只往对话里追加一句提示，用户以为配置生效了实际没有。这是诚信问题，比缺功能更糟。

**修复方案**：
1. 「应用此配置」二选一：
   - **实现**：将对话产出的配置调 `POST /api/ai/jobs/{id}/engine`（或相应端点）真正落库，按钮带确认反馈（toast「已应用到任务 X」）。
   - **下线**：删除按钮，避免误导。（建议先实现，工作量不大）
2. 概览 tab 重做（二选一）：
   - 做**独家聚合**：今日 AI 产出摘要（成功/失败任务数、最新 picks 前 3、待复盘数）+ 异常提醒（失败任务、inbox 积压）——强调"别处看不到的汇总与异常"。
   - 或直接砍掉概览 tab，默认进 Skill 工坊。
3. 配置 tab：引擎清单只读 + handoff 导流卡，要么补编辑能力（调 engine 端点），要么精简为一行状态说明。

**验收标准**：「应用此配置」点击后数据库中任务配置真实变更（或按钮已移除）；概览 tab 有独家信息或被移除。

---

## P4-3 Alerts / LimitUp / OpportunityPool 交互深化

**问题**：
- AlertsView 详情只有一句话原因，无确认/静默/跳转个股等任何动作。
- LimitUpView 梯队分组只显示龙头名，无法展开看组内个股；炸板池无联动。
- OpportunityPoolView 详情仅理由+风控标签，无动作；无 updated-at 显示。

**修复方案**（按价值排序，可分期）：
1. Alerts 详情：加「查看板块」（跳 SectorMonitor 对应板块）、「加入观察」两个动作即可闭环；确认/静默如需后端加字段则单独排期。
2. LimitUp 梯队：组行可展开显示组内个股列表（后端 payload 已有组内数据则纯前端展开；没有则标记后端补充）。
3. OpportunityPool 详情：加「加入观察」+ `updated-at` 传给 QueryState。
4. 各页详情面板补关键数字（现价、涨跌幅）——多数数据已在 payload 里，只是没渲染。

**验收标准**：三个页面的详情都有至少一个可执行动作，不再"看完就完了"。

---

## P4-4 HomeView 增强

**问题**：四张指标卡全是其他页复读；"AI 定时任务"纯链接卡占位；行动优先级只有标题+一句话。

**修复方案**：
1. 删链接占位卡。
2. 指标卡接真实环比（昨日对比），没有数据就不显示 trend（配合 P3-4）。
3. 行动优先级列表补：来源（来自哪个 AI 任务）、时间、点击跳详情。
4. （可选）加"今日异常"区块：采集失败、任务失败、数据延迟提醒——把运维状态显性化。

**验收标准**：首页每个元素都是真实数据或真实功能，无占位。

---

# P5 后端架构整理

> 以下改动较大，建议在 P0-P4 完成、测试套件恢复健康后分批进行。每批保持可独立发布。

## P5-1 后端中优先级 Bug 打包修

| # | 位置 | 问题 | 修法 |
|---|---|---|---|
| a | `services/home_dashboard.py:17-21` | 文件级 mojibake：「上证指数/深证成指/创业板指」是 UTF-8 被 GBK 错误转码的残体，fallback 名称输出乱码 | 修正字符串为正确 UTF-8；全文件检查其他乱码 |
| b | `services/skill_executor.py:466` | prefetch 用系统 `python3` 而非 `.venv`，依赖缺失时静默失败跑空数据 | 改 `sys.executable`；失败时让 skill 明确失败而非跑空数据 |
| c | `services/skill_executor.py:409-422` | `_find_new_output_files` 按 mtime 扫整个 inbox，多 job 重叠互相认领产出 | 按约定文件名（含 job/run id）精确匹配 |
| d | `services/realtime_cache.py:43-46` | `background_refresh=True` 死参数：置 "refreshing" 但无人发起刷新 | 实现后台刷新（scheduler 已有线程池）或删除参数 |
| e | `services/realtime_cache.py:105,249` | 每请求同步打腾讯行情（无缓存，timeout 20s） | 加短 TTL（5~10s）内存缓存 |
| f | `services/workspace.py:69`、`realtime_cache.py:380` | watchlist 全表 delete+insert，并发丢数据 | 改 upsert（`INSERT ... ON CONFLICT` / merge），P4-1 前置 |
| g | `services/news_service.py:415-495` | 查询层 O(n²) SequenceMatcher 聚类跑在请求线程 | 先按 title_hash 分桶再模糊比；candidate_limit 降配额 |
| h | `main.py:897-898` | catch-up 对 `*/2`、`8,12` cron 静默失效（int() ValueError 被吞） | 用 croniter 或解析首个触发时刻；except 里记日志 |
| i | `services/limit_up.py:150-164` | 涨停池无缓存，每端点打 3~4 次东财接口 | 加 30~60s 内存缓存（与 gateway 缓存层统一，见 P5-4） |
| j | `services/collector.py:58-63` | `float("--")` 炸掉整次采集 | try/except 返回 None；采集失败计数打点 |
| k | `main.py:173` | `engine.connect()` 未关闭 | 改 `with engine.begin() as conn:` |
| l | `ai_center.py:1008-1050` | inbox 扫描全量 glob+逐文件解析；processed/ 231 个文件无清理 | 定期清理 processed（保留 7 天）；扫描按 mtime 增量 |

**验收标准**：每项附带或更新测试；全量测试通过。

---

## P5-2 拆分 main.py（2248 行）与 ai_center.py（2024 行）

**问题**：main.py 混了 5 种职责（~60 个路由、scheduler 编排 300+ 行、SSE 子进程流 230 行、SQLite 恢复+手写 DDL 160 行、CLI 探测）；ai_center.py 是上帝类（skill/job/run/pick/rulepack/backtest/inbox 导入/outcome 计算）。

**修复方案**：
1. main.py 拆分为：
   - `app/routers/market.py`、`limit_up.py`、`ai_center.py`、`news.py`、`workspace.py`（routers/ 目录已有 auth.py，延续既有模式）
   - `app/scheduler.py`（job 定义 + catch-up 逻辑）
   - `app/skill_chat.py`（SSE 流，含 P0-7 修复）
   - `app/schema_migrations.py`（DDL 迁移，配合 P5-3）
2. ai_center.py 拆出 `ai_import.py`（scan/import_run）与 `ai_outcomes.py`（结果计算）。
3. 每拆一块跑全量测试 + 手工过一遍相关页面。
4. 顺带清理：CLI 查找逻辑 3 份重复（main.py:256-305 两份 + skill_executor.py:425）收敛一处；`SPA_NAVIGATION_PATHS`（main.py:57-69）要么使用要么删；walrus 恒真写法（main.py:1789,1817,1929）改正。

**验收标准**：main.py 降到 ~400 行以内（纯组装）；测试全过；各页面手工回归无异常。

---

## P5-3 Schema 管理统一

**问题**：`models.py`（SQLAlchemy）与 `main.py:168-253` `ensure_ai_center_schema`（手写 ALTER/CREATE）双轨并存，`AiSkillTemplate` 两处都定义，极易漂移。

**修复方案**（二选一）：
- **方案 A（轻量，推荐）**：统一到 SQLAlchemy——`ensure_ai_center_schema` 改为只做"对比现有列、缺则 ALTER"的自动迁移助手，表结构以 models.py 为唯一真相。
- **方案 B**：引入 Alembic 做正式迁移管理（一次性成本较高，长期最稳）。
- 附带：`models_auth.py`（18 行）并入 `models.py`。

**验收标准**：表结构只有一处定义；新加字段只需改一处。

---

## P5-4 缓存层与时区统一

**问题**：
- 四层缓存各自为政：gateway 内存(30s) / realtime_cache DB 快照(TTL 90s) / page_payloads 内存(180s) / market_temperature 内存(按分钟戳)；`individual_ttl=90s` vs 刷新间隔 120s，稳定产生"stale_cache"展示态。
- 全链路 naive `datetime.now()`，唯独 scheduler 用 Asia/Shanghai（main.py:683）——部署到 UTC 容器时交易时段/trading_date/新闻时间全部错位 8 小时。

**修复方案**：
1. 时区：新建 `app/time_utils.py` 提供 `now_cn()`（`datetime.now(ZoneInfo("Asia/Shanghai"))`），全链路替换；DB 存储保持 naive 但明确注释"存储为北京时间"，或迁 aware（评估迁移成本）。
2. 缓存：梳理四个缓存的 TTL 与失效语义，对齐到「刷新间隔 + 容忍 stale 时长」矩阵；至少修掉 90s vs 120s 的错位（TTL 改为 ≥ 刷新间隔 + 30s）。
3. 统一 `_to_float`：6+ 处各写一份且行为不一致（realtime_cache 版支持"万/亿"），收敛到 `app/utils.py`。

**验收标准**：`grep datetime.now()` 全部走 time_utils；页面不再出现常态化的 stale_cache 状态。

---

## P5-5 数据模型对齐用户体系 + 死代码清理

**问题**：
- watchlist/workspace/notes 全部全局单份（无 user_id），任何登录用户改动影响所有人——多用户表加了但数据模型没跟上。
- `stock_research.py` + `run_stock_research.py` 是已被 skill_executor 取代的旧管线（只被两个测试引用），半死代码。
- 依赖环：`home_dashboard.market_temperature = ...`（main.py:669-670）后补赋值。
- CustomExecutor `shell=True` + format 拼命令（skill_executor.py:365-381），认证用户可任意命令执行——设计如此，但需在文档/前端明示风险。

**修复方案**：
1. **决策**：单用户自用 → 删多用户表只留一个本地账户（最省事）；要多用户 → watchlist/notes 加 user_id 外键 + 迁移。**按实际使用场景决定，个人项目建议承认单用户**。
2. 删除 `stock_research.py`、`run_stock_research.py` 及对应测试引用。
3. 解环：market_temperature 通过构造函数注入 home_dashboard（或在 page_payloads 层组装）。
4. skill_executor 风险：在 AiCenter 引擎配置 UI 加明显提示「自定义命令拥有服务器完整权限」；文档注明。

**验收标准**：决策落地（表结构或用户表之一被清理）；死代码删除后测试全过。

---

## P5-6 测试补全

**问题**：auth 路由/中间件零测试；skill-chat SSE、scheduler catch-up、SQLite 恢复逻辑（最高危路径）零测试；market_temperature、market_signal、home_dashboard、workspace、skill_executor 无专项测试。

**修复方案**（按风险排序补）：
1. SQLite 恢复逻辑测试（配合 P0-2：locked 不删除、真损坏才恢复）。
2. auth：登录/改密/过期 token/权限中间件（含 P0-1 的 /api/page 401 用例）。
3. skill-chat SSE：心跳帧、进程结束、超时路径。
4. scheduler catch-up：普通 cron + `*/2` 异常 cron 两种形态。
5. 其余 service 各补核心路径 1~2 个用例。

**验收标准**：`pytest --cov=app tests/` 覆盖率明显提升；上述高危路径有用例守护。

---

## 附：执行节奏建议

| 阶段 | 内容 | 预计工作量 | 前置 |
|---|---|---|---|
| 第 1 批 | P0-1 ~ P0-8 全部 | 1~2 天 | 无，立即开始 |
| 第 2 批 | P1-1 ~ P1-5 | 半天 | 与第 1 批可并行 |
| 第 3 批 | P2-1 ~ P2-8 | 1~2 天 | 无 |
| 第 4 批 | P3-1 ~ P3-5 | 2~3 天 | P2 完成后更顺 |
| 第 5 批 | P4-1 ~ P4-4 | 2~3 天 | P4-1 依赖 P5-1f（upsert） |
| 第 6 批 | P5-1 ~ P5-6 | 3~5 天 | 测试套件健康（P0-8）后 |

> 原则：每批改完跑 `.venv/bin/python -m pytest tests/ -q` + 前端 `npm run build:spa` + 手工过一遍相关页面，再进下一批。
