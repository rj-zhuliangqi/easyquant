# 选股器（Stock Screener）技术方案 v2

> 目标：在 easyquant 现有架构上，增加一个可配置的 A 股选股工具，支持近一个月（约 20–30 个交易日）的日线技术指标、量能形态、资金流向组合筛选，并提供 6 套开箱即用的策略预设。
>
> v2 为评审优化版：修正了 v1 中与现有代码不符的假设（实时快照字段、复权口径、回补窗口），补充了性能与限流策略。

---

## 0. 评审修订记录（v1 → v2）

| # | v1 的问题 | 评审结论 | v2 修正 |
|---|---|---|---|
| 1 | 假设 `fetch_individual_realtime()` 能提供 PE/PB/市值/换手率 | **不成立**。东财 clist 当前只取 `f12,f14,f2,f3,f62`（代码/名称/最新价/涨跌幅/主力净额），见 `app/akshare_client.py:455` | 扩展 clist fields 为 `f12,f14,f2,f3,f62,f8,f9,f23,f20,f21`（换手率/市盈动/市净率/总市值/流通市值），一次调用零额外成本；字段失效时基础组指标降级为 null + warnings |
| 2 | 日线数据主路径 `adjust=""`（不复权），fallback 东财 `fqt=1`（前复权），两路径口径混用 | 除权日附近 MA/连涨/涨跌幅会断裂，且同库中不同股票口径不一致 | `fetch_stock_daily_history` 增加 `adjust` 参数（默认 `""` 保持兼容），选股器统一传 `"qfq"`；东财 fallback 已是 `fqt=1`，口径一致 |
| 3 | 回补窗口 45 自然日 ≈ 30 个交易日 | **不足以计算 MA60**；MACD(12,26,9) 的 EMA 预热也需要更长历史 | 回补窗口改为 **150 自然日（≈100 交易日）**；DB 保留最近 120 个交易日，每日回补后清理更早数据 |
| 4 | 资金流与技术数据回补绑在一起 | 资金流是第二轮 ~2000 次调用，阻塞技术筛选可用时间 | 解耦为两个阶段/两个进度；资金流未就绪时，资金类条件降级（跳过该条件 + 返回 warnings），技术筛选立即可用 |
| 5 | 回补无防限流策略 | 东财/akshare 有反爬，串行狂拉可能被封 | 串行 + 每只间隔 0.2–0.3s 抖动；单只失败记录后继续，不中断整体；支持断点续跑（按日期缺口补） |
| 6 | 手动回补与定时任务可能并发 | SQLite 写入冲突/重复拉取 | `DailyBarsService.progress["running"]` 互斥锁，运行中拒绝第二次触发 |
| 7 | 每次筛选全量读 24 万行进 pandas | 实测可接受（<1s），但并发筛选时浪费 | 增加特征帧内存缓存：以 `latest_trading_date` 为 key，TTL 10 分钟，回补完成时失效 |
| 8 | 「放量突破」预设用 `涨幅 < 9.5%` 排除涨停 | 对创业板/科创板（20cm）误伤 | 改用 `limit_up_today == 0`（引擎按代码前缀自动判定 10%/20% 涨停），全板块兼容 |
| 9 | 「主力抢筹」预设用绝对值 5000 万 | 天然偏向大盘股 | 增加指标 `main_net_inflow_5d_pct_mv`（5 日主力净流入 ÷ 流通市值），预设改用 `> 0.5%` |
| 10 | 未说明数据时点 | 用户可能误以为盘中实时 | 明确：筛选基于**最近一个完整交易日**收盘数据；盘中执行用的是前一交易日结果，页面显著标注数据日期 |

---

## 1. 现状与关键约束

- **后端**：FastAPI 单体，`app/main.py` 内联约 95 个路由，服务位于 `app/services/`。
- **数据源**（`app/akshare_client.py` 的 `AkshareGateway`）：
  - `fetch_stock_daily_history(symbol, start, end)`：个股日线 OHLCV/涨跌幅/换手率（**当前不复权**，v2 将加 `adjust` 参数）；
  - `fetch_stock_fund_flow_history(stock, market)`：个股资金流历史，**一次调用返回约 100 个交易日**（回补成本 = 每股票 1 次调用）；
  - `fetch_individual_realtime()`：全市场快照（30s 缓存），**当前无 PE/PB/市值字段**，v2 将扩展。
- **数据库**：SQLite（WAL）。目前无个股级日线 OHLCV 表，只有盘中分钟级快照 `individual_stock_snapshots`。
- **前端**：Vue3 SPA（`frontend/src`），手写 CSS 设计系统，`vue-router` + `@tanstack/vue-query`。
- **调度**：`BackgroundScheduler`（`app/main.py:569`），`_run_scheduled_job` 包裹模式。

**核心约束**：逐只拉取日线做同步筛选不可行（0.5–1.5s/只）。必须落地本地日线库 + 后台回补，筛选引擎离线计算。

---

## 2. 总体架构

```
前端 ScreenerView.vue
  │  POST /api/screener/run · GET /indicators · GET/POST/DELETE /presets
  │  GET /status · POST /backfill
  ▼
FastAPI 路由层（app/main.py）
  ├── ScreenerService    — 指标注册表 / 特征计算(带缓存) / DSL 过滤 / 内置策略
  └── DailyBarsService   — 股票池 / 日线回补 / 资金流回补 / 覆盖统计 / 进度互斥
        │                        │
        ▼                        ▼
  stock_daily_bars        stock_fund_flow_daily      （SQLite，各保留 120 交易日）
  screener_presets
  ▲
  └── 调度：收盘后 15:40 增量回补；启动时数据过期则补偿回补
```

---

## 3. 数据层

### 3.1 新增表（app/models.py）

**`StockDailyBar`（`stock_daily_bars`）**：`stock_code`、`trading_date`、`open/close/high/low`、`volume`、`amount`、`change_pct`、`turnover_rate`；`UniqueConstraint(stock_code, trading_date)`，索引 `(stock_code, trading_date)`、`(trading_date)`。价格统一**前复权**口径（成交量/成交额/换手率为原始值）。

**`StockFundFlowDaily`（`stock_fund_flow_daily`）**：`stock_code`、`trading_date`、`main_net_amount`（主力净流入，元）、`main_net_ratio`（净占比 %）、`super_large_net`（超大单，元）、`large_net`（大单，元）；同样 `(code, date)` 唯一。

**`ScreenerPreset`（`screener_presets`）**：`name`、`description`、`conditions_json`、`universe_json`、`order_by`、`order`、`is_builtin`、`created_at`。

### 3.2 Gateway 调整（`app/akshare_client.py`，最小改动）

1. `fetch_stock_daily_history(symbol, start, end, adjust="")`：新增 `adjust` 形参透传给 `ak.stock_zh_a_hist`；默认 `""` 不影响现有调用方（`StockResearchService` 等）。
2. `_fetch_individual_realtime_eastmoney` 的 clist `fields` 扩展为 `f12,f14,f2,f3,f62,f8,f9,f23,f20,f21`，映射新增列：`turnover_rate`、`pe_dynamic`、`pb`、`total_mv`、`float_mv`。列解析失败时保持旧行为（只少新列），并在 `_source_snapshots` 记 degraded。
3. `_standardize_columns` 增加对应中→英列名映射。

### 3.3 `DailyBarsService`（`app/services/daily_bars.py`）

注入 `gateway`、`now_provider`；upsert 复用 `_common.merge_upsert_by_key`。

- `get_universe(session, min_amount=50_000_000)`：取最新 `individual_stock_snapshots`（fallback 实时快照），过滤 ST/*ST/退市、北交所（4/8/920 开头）、停牌（成交额为 0）、`amount >= min_amount`（默认 5000 万，约 2000–2500 只）。
- `ensure_recent_bars(session, codes, days=150, progress_cb=None)`：逐只比对 DB 已有日期，只补缺口；`adjust="qfq"`；单只间隔 0.2–0.3s 随机抖动；失败记录到 `progress["failed"]` 并继续。
- `update_fund_flow(session, codes, progress_cb=None)`：同理补资金流（一次调用取全量历史，按日期 upsert）。
- `backfill_all(session, min_amount=..., days=150)`：阶段一全量日线 → 阶段二资金流；`self.progress = {"running", "stage", "done", "total", "failed": [...], "message"}`，运行中加互斥。
- `prune_old_bars(session, keep_trading_days=120)`：每次回补后删除更早数据。
- `coverage(session)`：`{"stock_count", "latest_date", "bar_rows", "flow_rows", "flow_stock_count"}`。

### 3.4 调度（`app/main.py` 新增，仿现有 `add_job` 模式）

- **收盘增量**：cron 周一到周五 15:40，`ensure_recent_bars(days=10)` + `update_fund_flow` + `prune_old_bars`（约 30–40 分钟）。
- **启动补偿**：`latest_date` 为空或落后 > 5 个交易日 → `date` trigger 启动后即跑全量回补（仿 `main.py:675` 模式）。
- 两个入口都经 `DailyBarsService` 互斥锁，避免并发。

---

## 4. 筛选引擎（`app/services/screener.py`）

### 4.1 计算模型

- 从 DB 读 universe 的日线（最近 120 交易日）+ 资金流（最近 15 日聚合），pandas 分组计算**特征行**（每股一行 = 最新交易日的全部指标值）。
- **特征帧缓存**：`(latest_date, universe_hash)` 为 key 的内存缓存，TTL 10 分钟；回补完成主动失效。
- 条件 DSL 过滤 → join 实时快照的基础字段（PE/PB/市值，仅当条件引用时）→ 排序截断返回。
- **数据时点**：筛选基于最近**完整交易日**；结果中返回 `data_date`，前端显著展示。
- **资金流降级**：某股票资金流缺失时，资金类条件对该股票记为不满足；若全库资金流为空，跳过资金类条件并在 `warnings` 说明。

### 4.2 指标注册表（6 组 ~36 项）

| 分组 | 指标（name） |
|---|---|
| 基础 basic | `latest_price`、`change_pct`、`total_mv`、`float_mv`、`pe_dynamic`、`pb`、`turnover_rate` |
| 趋势 trend | `ma5/ma10/ma20/ma60`、`close_vs_ma5/10/20/60`（乖离%）、`ma_bullish`（多头排列 0/1）、`golden_cross_recent`（近 5 日 MA5 上穿 MA10）、`death_cross_recent`、`high_20d_break`、`high_60d_break`、`low_20d_break` |
| 动量 momentum | `change_3d`、`change_5d`、`change_10d`、`change_20d`、`consecutive_up_days`、`consecutive_down_days`、`rsi6`、`rsi14`、`macd_dif`、`macd_dea`、`macd_hist`、`macd_golden_recent`（近 3 日）、`bias20` |
| 量能 volume | `volume_ratio`（当日量 ÷ 前 5 日均量，不含当日）、`amount`、`amount_ma5`、`turnover_ma5`、`volume_up_days`（连续放量天数） |
| 形态 pattern | `limit_up_today`（按前缀判定：300/301/688/689 → 19.8%，其余 9.8%）、`limit_up_count_5d`、`platform_breakout`（收盘 > 前 20 日最高价）、`gap_up_pct`、`lower_shadow_ratio` |
| 资金流 fundflow | `main_net_inflow`、`main_net_inflow_5d`、`main_net_inflow_10d`、`main_net_inflow_days`（连续净流入天数）、`main_net_ratio`、`super_large_net`、`main_net_inflow_5d_pct_mv`（占流通市值 %） |

注册表条目：`{"name","label","group","unit","description","default_op","default_value"}`，金额类单位统一为元（前端展示时格式化为 万/亿）。

### 4.3 条件 DSL

```json
{
  "conditions": [
    { "indicator": "consecutive_up_days", "op": ">=", "value": 4 },
    { "indicator": "volume_ratio",        "op": "between", "value": [1.5, 4] },
    { "indicator": "close_vs_ma20",       "op": ">=", "value": 0 },
    { "indicator": "main_net_inflow_5d",  "op": ">",  "value": 0 }
  ],
  "universe": { "min_amount": 50000000, "exclude_st": true, "boards": ["main","cyb","kcb"] },
  "order_by": "main_net_inflow_5d", "order": "desc", "limit": 100
}
```

- 操作符：`> >= < <= == between`；0/1 布尔指标用 `== 1`。
- 板块映射：`main` = 60/00 开头，`cyb` = 30 开头，`kcb` = 688/689 开头；北交所恒排除。
- 结果行固定字段：`code/name/close/change_pct/turnover_rate/volume_ratio/amount/main_net_inflow/main_net_inflow_5d` + 条件引用的指标值。

---

## 5. API（内联 `app/main.py`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/screener/indicators` | 指标注册表 + 分组 |
| POST | `/api/screener/run` | 执行筛选；响应含 `data_date`、`total`、`results`、`warnings` |
| GET | `/api/screener/presets` | 预设列表 |
| POST | `/api/screener/presets` | 保存自定义预设 |
| DELETE | `/api/screener/presets/{id}` | 删除（内置返回 403） |
| GET | `/api/screener/status` | `coverage` + `progress`（两阶段进度） |
| POST | `/api/screener/backfill` | 后台线程触发回补；`{"started": true, "already_running": bool}`；运行中返回 `already_running` |

外壳路由 `@app.get("/screener")`；预设 seed 在启动时按 `name` 幂等写入（`is_builtin=1`）。

---

## 6. 前端（`frontend/src/views/ScreenerView.vue`）

- **顶部**：`PageHero` + 数据状态条（覆盖股票数 / 数据日期 `data_date` / 回补进度条），缺数据时引导「更新数据」并轮询 `/status`。
- **预设条**：6 个内置策略 chip（hover 显示一句话说明与适用行情）+ 自定义预设（可删）。
- **条件构建器**：分组 → 指标 → 比较符 → 数值（`between` 双输入；布尔指标固定 `== 1`）；已选条件为可删标签；股票池：排除 ST（默认开）、板块勾选、最低成交额档位。
- **结果列表**：`row-card`（代码/名称/现价/涨跌幅/换手率/量比/5 日主力净流入/条件指标值），列头排序，行尾「加自选」（复用 workspace 接口）。
- 金额字段统一在前端格式化为 万/亿。
- 接线：`router.js` 加 `/screener`（`keepAlive`）→ `AppSidebar.vue` 加导航「选股器」→ `main.py` 加外壳路由 → `npm run build:spa`。

---

## 7. 内置策略预设（6 套，v2 修订）

| # | 策略 | 条件（DSL 语义） | 适用场景 |
|---|---|---|---|
| 1 | 放量突破 | `platform_breakout==1` ∧ `volume_ratio ∈ [2,5]` ∧ `change_pct >= 3` ∧ **`limit_up_today==0`** ∧ `close_vs_ma20 >= 0` ∧ `main_net_inflow > 0` | 量价资金三重确认突破；不追涨停，兼容 20cm 板块 |
| 2 | 趋势多头 | `ma_bullish==1` ∧ `close_vs_ma20 >= 0` ∧ `change_20d ∈ [5,35]` ∧ `turnover_rate ∈ [3,15]` ∧ `main_net_inflow_5d > 0` | 顺势低吸，震荡向上市 |
| 3 | 连续小阳 | `consecutive_up_days >= 4` ∧ `change_pct < 5` ∧ `change_10d < 18` ∧ `volume_ratio ∈ [1,2.5]` ∧ `close_vs_ma10 >= 0` | 温和吸筹，回避急涨 |
| 4 | 缩量回踩 | `close_vs_ma20 ∈ [-3,3]` ∧ **`change_3d < 0`** ∧ `volume_ratio <= 0.7` ∧ `change_20d > 10` ∧ `macd_dif > 0` | 上升趋势中的缩量回调买点 |
| 5 | 主力抢筹 | `main_net_inflow_days >= 3` ∧ **`main_net_inflow_5d_pct_mv > 0.5`** ∧ `change_5d < 20` ∧ `rsi14 < 75` | 资金先行、价格未充分拉升；市值归一化避免偏大盘 |
| 6 | 超跌反弹 | `change_20d < -15` ∧ `rsi14 < 30` ∧ `volume_ratio >= 1.5` ∧ `change_pct > 0` | 左侧反弹，需配合仓位控制 |

---

## 8. 测试计划

- `tests/test_daily_bars.py`：
  - universe 过滤（ST/北交所/低成交额/停牌剔除）；
  - `ensure_recent_bars` 幂等（重复回补无重复行）、日期缺口检测、`prune_old_bars` 保留窗口；
  - **断言 gateway 调用带 `adjust="qfq"`**（复权口径回归）；
  - 互斥锁：`running=True` 时第二次 `backfill_all` 直接拒绝。
- `tests/test_screener.py`（合成日线 + fake gateway）：
  - 连涨天数、量比（前 5 日均量不含当日）、MA 关系、平台突破、涨停判定（600 vs 300 不同阈值）；
  - RSI/MACD 数值与已知基准比对；
  - DSL 各操作符与多条件组合、板块过滤、资金流缺失降级（warnings）；
  - 6 套内置预设全部可执行；
  - 性能冒烟：2000 只 × 120 交易日合成数据，特征计算 < 3s。
- API 回归：沿用 `conftest.py` 的 `create_app(session_factory=..., gateway=fake, enable_scheduler=False)` 模式。
- 构建：`npm run build:spa` 通过。
- 冒烟：启动应用 → `POST /api/screener/backfill`（可先用成交额 Top 500 缩小范围）→ 用「放量突破」执行一次，检查结果合理性。

---

## 9. 实施顺序

1. Gateway 微调（`adjust` 参数 + clist 字段扩展）+ 单测。
2. `models.py` 三张新表 + `DailyBarsService`（含互斥/prune）+ 单测。
3. `ScreenerService`（注册表/特征计算/缓存/DSL/预设）+ 单测。
4. `main.py`：API、调度、预设 seed、外壳路由。
5. 前端页面 + 路由/导航 + `build:spa`。
6. 全量 pytest + 真实数据冒烟。

---

## 10. 风险与回退

| 风险 | 缓解 |
|---|---|
| 首次回补 ~4000 次调用（日线+资金流），约 60–90 分钟 | 后台线程 + 前端进度展示；技术数据先行，资金流第二阶段；断点续跑 |
| akshare/东财限流 | 串行 + 0.2–0.3s 抖动；失败记录不中断；次日增量任务自然补漏 |
| 东财 clist 扩展字段失效 | 列解析失败退回旧字段集合并记 degraded；基础组指标返回 null + warnings |
| 除权日数据口径 | 统一 qfq；单测守护 `adjust="qfq"` 调用 |
| 数据体积 | 2000 只 × 120 日 ≈ 48 万行（两表合计），SQLite WAL 可承受；每日 prune |
| 回退 | 功能为纯新增：新表、新路由、新页面。回退 = 删路由/导航/表即可，不影响既有功能 |
