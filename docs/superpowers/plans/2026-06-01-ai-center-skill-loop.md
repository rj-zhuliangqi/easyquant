# AI 中台与 Skill 闭环系统实施方案

## Summary
在现有项目中新增独立的 `AI 中台`，把你每天的 cron skill 流水线沉淀为一个可展示、可复盘、可版本管理、可历史重跑的闭环系统。第一版覆盖四件事：每日任务结果展示、`AI 相关能力` 聚合展示、T+1/T+3 自动复盘、数据库内置 skill revision 管理，并支持按历史日期重跑 skill 做版本对比。

产品入口统一放在 `AI 中台`，内部先做 4 个标签：
`任务结果`、`AI 相关能力`、`复盘沉淀`、`Skill 版本`。
其中 `AI 相关能力` 是默认首页，用来承接当天由不同 skill 产出的股票机会、标签、命中关系和后续表现。

## Key Changes
### 1. 数据模型
新增一组 AI 闭环表，数据库继续使用 SQLite：

- `ai_skill`
  保存 skill 的逻辑身份，如 `集合竞价分析`、`尾盘选股`、`超短线盘后选股`。
  字段：`id`、`name`、`category`、`enabled`、`description`、`created_at`。

- `ai_skill_revision`
  保存 skill 的数据库内置版本快照，作为版本真源。
  字段：`id`、`skill_id`、`revision_no`、`title`、`content_text`、`config_json`、`change_note`、`status(draft/active/archived)`、`created_at`。
  约束：同一 skill 仅一个 `active` revision；历史 revision 不可覆盖，只能新增。

- `ai_job`
  保存定时任务定义，对应你现有 cron job 清单。
  字段：`id`、`name`、`schedule_label`、`schedule_rrule_or_cron`、`skill_id`、`active_revision_id`、`enabled`、`created_at`。
  作用：任务和 skill 解耦，一个 skill 可被多个 job 复用；切换版本只改 job 的 `active_revision_id`。

- `ai_run`
  保存每次真实执行或历史重跑的 run 记录。
  字段：`id`、`job_id`、`skill_id`、`revision_id`、`run_type(production/backtest)`、`trading_date`、`started_at`、`finished_at`、`status`、`source_input_ref`、`raw_output_text`、`structured_summary_json`、`error_text`。
  约束：run 写入后绑定的 `revision_id` 不再改变。

- `ai_pick`
  保存 run 里拆出的推荐项，是闭环分析核心表。
  字段：`id`、`run_id`、`trading_date`、`stock_code`、`stock_name`、`sector_name`、`pick_type`、`confidence_score`、`reason_summary`、`tags_json`、`priority_rank`。
  设计：同一只股票同日可被多个 run 命中，不做硬去重；页面层聚合展示。

- `ai_pick_outcome`
  保存每条推荐的自动评估结果。
  字段：`id`、`pick_id`、`window(T+1/T+3)`、`open_change_pct`、`close_change_pct`、`max_gain_pct`、`max_drawdown_pct`、`hit_limit_up`、`beat_benchmark`、`outcome_label`、`computed_at`。
  约束：每个 `pick_id + window` 唯一。

- `ai_review_note`
  保存人工复盘补充。
  字段：`id`、`pick_id`、`window`、`review_text`、`review_tags_json`、`is_expectation_met`、`failure_reason`、`improvement_hint`、`created_at`。

- `ai_backtest_batch`
  保存历史重跑批次。
  字段：`id`、`skill_id`、`revision_id`、`date_from`、`date_to`、`status`、`created_at`、`summary_json`。
  每次批量重跑生成一组 `ai_run(run_type=backtest)` 和对应 picks/outcomes，和真实生产 run 分开统计。

### 2. 输入与执行链路
第一版继续沿用你现有的 Codex 定时任务执行 skill，本项目先负责“接收结果、管理版本、沉淀复盘”。

- 生产运行入口
  以“文件落地导入”为主入口。
  每个 cron skill 跑完输出一个标准结果文件，项目定时扫描导入。
  标准文件包含：`job_name`、`skill_name`、`revision_id or revision_no`、`trading_date`、`run_type`、`raw_output`、`structured_picks[]`、`metadata`。

- revision 绑定
  每次生产 run 必须显式携带 revision 标识；导入时只允许解析到唯一 revision。
  禁止按当前 active revision 反推历史 run。

- 自动评估
  新增后台 job，每天收盘后或次日固定时间计算前一交易日 picks 的 `T+1`、`T+3` outcome。
  第一版优先覆盖：开盘涨跌、收盘涨跌、最大涨幅、最大回撤、是否涨停、是否跑赢基准。

- 历史重跑
  新增 backtest runner：选择 `skill + revision + 日期区间` 后，对每个交易日生成独立 `backtest` run。
  backtest 和 production 复用同一套表结构，但查询统计必须显式区分。

### 3. API / 页面
新增 `AI 中台` 页面和一组 API，延续当前 FastAPI + 静态页面模式。

页面结构：
- `AI 中台 / AI 相关能力`
  默认首页。
  展示当天聚合推荐、来源 skill、来源 revision、命中次数、核心理由、T+1/T+3 结果入口。
  这里不只看“推荐”，还要承接题材、标签、强弱判断、来源任务等 AI 产出能力。

- `AI 中台 / 任务结果`
  展示 cron job 清单、最近运行状态、耗时、错误、原始输出、结构化摘要、使用 revision。
  支持按任务名、交易日、状态筛选。

- `AI 中台 / 复盘沉淀`
  展示推荐结果统计、成功/失败标签、人工复盘、经验总结。
  支持按 skill、revision、日期、标签过滤。

- `AI 中台 / Skill 版本`
  展示每个 skill 的 revision 时间线、change note、当前 active 版本。
  支持“设为 active”“回退到旧版本”“发起历史重跑对比”。

核心 API：
- `GET /api/ai/jobs`
- `GET /api/ai/runs`
- `GET /api/ai/runs/{id}`
- `POST /api/ai/import-run`
- `GET /api/ai/picks`
- `GET /api/ai/picks/{id}/review`
- `POST /api/ai/picks/{id}/review`
- `GET /api/ai/skills`
- `POST /api/ai/skills/{id}/revisions`
- `POST /api/ai/jobs/{id}/activate-revision`
- `POST /api/ai/backtests`
- `GET /api/ai/backtests`
- `GET /api/ai/insights/summary`

公共接口变化：
- 新增 `run_type`，区分 `production` 与 `backtest`。
- 新增 `revision_id`，作为 AI 结果的强制归因字段。
- 新增 `window` 维度，第一版固定支持 `T+1`、`T+3`。

### 4. 实施顺序
按最小可用闭环拆成 5 个阶段执行：

1. 基础数据层
   新增 AI 相关表、SQLite 索引、基础 repository/service。
2. 结果导入链路
   实现标准结果文件导入、run/pick/revision 绑定、失败记录。
3. 中台展示
   先做 `任务结果` 和 `AI 相关能力` 两个标签，形成可见结果面板。
4. 复盘闭环
   实现 T+1/T+3 自动 outcome 计算、人工复盘录入、统计汇总。
5. 版本与回测
   实现 revision 管理、job 激活切换、历史日期重跑、版本对比视图。

## Test Plan
需要覆盖的关键场景：

- 导入生产 run
  给定一个标准 skill 结果文件，正确创建 `ai_run`、多条 `ai_pick`，并绑定准确 revision。
- 同股多来源
  同一交易日同一股票被两个 skill 命中，系统保留两条 pick，`AI 相关能力` 聚合页正确显示多来源命中。
- revision 回退
  将 job 从新 revision 切回旧 revision，只影响后续 run；历史 run 保留原 revision。
- 自动 outcome 计算
  对已有 pick 正确生成 `T+1`、`T+3` outcome；重复执行不重复写入。
- 人工复盘
  为某 pick 补充 review note 后，详情页和聚合统计都能读到。
- 历史重跑
  创建 backtest batch 后，生成一组 `run_type=backtest` runs；其统计与 production 隔离。
- 版本对比
  同一 skill 的两个 revisions 在同一日期区间的命中率、平均涨跌、成功标签分布可并排查询。
- 异常导入
  缺少 revision、股票代码为空、结构化 picks 非法时，run 标记失败并记录错误，不污染正式数据。

## Assumptions
- 第一版继续由你现有的 Codex 定时任务实际执行 skill，本项目先不接管这些任务的调度执行。
- skill 版本真源放在数据库，revision 采用不可变快照；更新 skill 通过“新增 revision”完成，不原地改历史版本。
- 历史重跑第一版就做，但定位为“skill 决策回测”，不是完整交易撮合回测。
- 自动复盘窗口默认固定为 `T+1`、`T+3`。
- 数据库继续使用 SQLite 起步；若历史重跑和并发导入明显增多，再评估迁移方案。
