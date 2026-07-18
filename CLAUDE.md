# EasyQuant

A 股 AI 工作台 — 围绕 A 股交易日「盘前 → 盘中 → 盘后 → 夜间 → 周报」全时段，由
12 个 AI Skill（Claude Code CLI 驱动）+ AKShare 实时资金面 + 人工观察台共同构成
的本地决策面板。

## 技术栈

- **后端**：Python 3.11+, FastAPI, SQLAlchemy 2.0, APScheduler, SQLite(WAL),
  AKShare, PyJWT；包管理 `uv`
- **前端**：Vue 3 + Vue Router 4 + @tanstack/vue-query + ECharts + Vite 6
- **AI 执行**：Claude Code CLI（主）/ Goose CLI / 自定义脚本，通过 `subprocess`
  调起 → 写 `data/ai_center/inbox/*.json` → APScheduler 每 2 分钟扫描入库
- **部署**：macOS launchd + cloudflared tunnel，公网 `https://easyquant.vip`

## 目录约定

```
app/                    # FastAPI 后端
  main.py               # 入口（巨型 create_app，所有路由 + APScheduler 注册）
  models.py             # SQLAlchemy ORM
  ai_center_registry.py # BUILTIN_AI_JOBS — 12 个内置定时任务清单
  akshare_client.py     # AKShare 数据网关
  services/             # 业务服务层
    ai_center.py        # AI 任务/产物/复盘核心
    skill_executor.py   # Claude/Goose/Custom 执行引擎
    page_payloads.py    # 每个前端页面一次性 bootstrap 聚合
    ...（板块/涨停/工作台/温度/历史等）
  routers/auth.py       # JWT 鉴权
  static/spa/           # Vite 构建产物（前端最终落点）
frontend/               # Vue3 SPA 源码
  src/
    main.js, App.vue, router.js, styles.css
    views/              # 每个页面一个 .vue
    components/         # 共享组件 + ui/ 设计系统单元
    lib/                # api / auth / formatters
.claude/skills/         # AI Skill 提示词集（每个一份 SKILL.md）
data/
  sector_fund_monitor.db       # 主 SQLite（启动 integrity check；仅确认损坏才恢复，撞锁只重试不删 WAL）
  ai_center/inbox/             # AI 任务产物落点（待入库）
  ai_center/processed/         # 已入库归档
  ai_center/inbox/_failed/     # 入库失败的产物（含原始 JSON 便于排错）
scripts/
  fetch_data.py / run_skill.sh / debug_*.py
  experiments/          # 一次性数据探针、策略验证脚本（不发布、不测试）
tests/                  # pytest 测试集
docs/                   # 数据源调研 / 部署文档
```

## 常用命令

```bash
# 启动（开发）
bash start.sh                                    # 跑 uvicorn 在 8010 端口

# 启动（生产）— 使用 launchd 而不是 start.sh（避免 PID 管理冲突）
launchctl unload ~/Library/LaunchAgents/com.easyquant.server.plist
launchctl load   ~/Library/LaunchAgents/com.easyquant.server.plist
sleep 25  # akshare 启动慢
curl https://easyquant.vip/api/status

# 前端构建（每次改 frontend/ 后必跑）
npm run build:spa

# 跑测试
uv run pytest tests/ -q                          # 全套
uv run pytest tests/test_ai_center.py -q         # 单个文件

# 手动跑一个 AI Skill
./scripts/run_skill.sh 早盘复盘 2026-06-23
```

## 关键链路

1. **定时任务触发**：APScheduler 按 cron 触发 → `_execute_ai_skill_job(job_id)`
   → `claude -p <prompt>` subprocess → 写 `data/ai_center/inbox/<file>.json`
2. **产物入库**：APScheduler 每 2 分钟跑 `ai-run-import-scan` →
   `AiCenterService.scan_import_directory` → `import_run` → 写 `ai_runs` /
   `ai_picks` / `ai_trading_day_reviews` 表；失败的 JSON 移到 `inbox/_failed/`
3. **前端消费**：Vue Query 拉 `/api/page/<name>` 或 `/api/ai/...` →
   渲染时间线/卡片/表格

## 鉴权

- JWT bearer token（密钥自动生成并持久化到 `data/.jwt_secret`，或用 `EQ_JWT_SECRET`
  环境变量覆盖；默认 7 天有效）
- 密码哈希用 PBKDF2-HMAC-SHA256；旧 SHA-256 哈希在登录时无感迁移
- 首次启动无用户时创建默认管理员 `admin`，**初始密码随机生成并打印到启动日志**
  （仅首次；登录后请立即改密）
- 除 `/api/auth/*`、`/api/status` 外所有 `/api/*`（含 `/api/page/*`）均受
  AuthMiddleware 保护；token 校验在线程池查库，不阻塞事件循环

## 协作约定

- 写代码时**匹配现有风格**（看周围代码再改）
- 改前端必须 `npm run build:spa` 后再重启服务
- 每次重大改动开独立分支 `feature/<name>`，commit message 用中文
  `feat/fix/chore(scope): ...`
- SQLite schema 修改前备份 `data/sector_fund_monitor.db`
- 一次性实验脚本放 `scripts/experiments/`，不要丢在仓库根
- **启动方式只保留 launchd 一种**：不要用 `start.sh` 与 launchd 并存
  （双进程撞锁曾导致 DB 连环损坏；P0-2 已修但仍应避免锁竞争）
- 脚本访问主库一律用只读连接
  `sqlite3.connect("file:data/sector_fund_monitor.db?mode=ro", uri=True)`；
  写库走 app 服务层，不要裸连
- 不要在仓库根留 `.tmp_*` / 一次性脚本（`.gitignore` 已忽略，仍请主动清理）
