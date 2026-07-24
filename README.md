# EasyQuant — A 股 AI 工作台

一个本地运行的 A 股决策面板：把「盘前消息面 → 集合竞价 → 弱转强候选/确认 → 早盘
复盘 → 尾盘选股 → 超短复盘 → 夜间选股 → 持仓复盘」这条完整的交易日工作流，
交给 13 个 AI Skill（由 Claude Code CLI 驱动）按时段自动执行，产物经统一的
入库 / 展示管线送到前端面板。

> 📍 项目从最初的「板块资金监控小工具」演化而来 — 资金面采集仍然是核心数据
> 基础，但工作流的重心已经转移到 AI 时段化任务。

## 主要功能

- **首页时间线** — 当日 8 个时段的 AI 任务卡，已完成/失败/未执行状态一览，
  支持「立即执行」按钮和「查看详情」跳转
- **消息面页** — 每天 08:20 由 AI 拉东财/新浪/同花顺多源新闻并归纳为
  头条 / 市场影响 / 题材关注
- **AI 中台** — 任务运行管理、Skill 工坊（对话式调试）、选股池、回测、
  复盘经验沉淀
- **复盘** — 早盘 / 超短 / 持仓 / 周度复盘的结构化展示
- **板块资金监控** — 分钟级 industry/concept 资金流采样 + 排行 + 下钻
- **A 股连板梯队** — 涨停梯队、破板池、市场温度
- **个人观察台** — 自选关注 + 笔记
- **JWT 鉴权 + 用户管理**

## 启动

```bash
# 1. 安装依赖
uv sync
npm install

# 2. 构建前端（每次改 frontend/ 后必跑）
npm run build:spa

# 3. 启动后端
bash start.sh
# 默认监听 127.0.0.1:8010
```

浏览器打开 <http://127.0.0.1:8010> — 默认管理员 `admin / admin123`，**首次登录
后请改密码**。

## 生产部署

参见 [`docs/cloudflare-tunnel-deployment.md`](docs/cloudflare-tunnel-deployment.md)
— launchd plist + cloudflared tunnel，公网通过 `https://easyquant.vip` 访问。

```bash
launchctl unload ~/Library/LaunchAgents/com.easyquant.server.plist
launchctl load   ~/Library/LaunchAgents/com.easyquant.server.plist
```

## 架构概览

参见 [`CLAUDE.md`](CLAUDE.md)（顶层）。简单说：

```
APScheduler → claude -p <prompt> → data/ai_center/inbox/*.json
                                      ↓ (每 2 分钟扫描)
                                  ai_runs / ai_picks / ai_trading_day_reviews
                                      ↓
                                  /api/page/* + /api/ai/*  →  Vue3 SPA
```

## 测试

```bash
uv run pytest tests/ -q
```

## 协作

- 改动用 `feature/<name>` 分支，commit message 中文 `feat/fix/chore(scope): ...`
- 一次性实验脚本放 `scripts/experiments/`，不要扔在仓库根
- SQLite schema 改动前备份 `data/sector_fund_monitor.db`
