# EasyQuant 数据源切换 TuShare + 策略对标通达信 完整优化方案 (P0+P1+P2)

> 调研日期 2026-07-23 | 已用 TuShare 2000 档 token 实测权限 + 精读数据源/选股引擎代码
> 分支建议：`feature/tushare-strategy-upgrade`（从 `feature/screener-rebuild` 切出）

---

## 一、调研结论速览

### 1.1 TuShare 2000 档实测权限边界（已用 token `b90c...` 实测，非文档推测）

| 数据域 | TuShare 接口 | 实测结果 | 单位（需换算）|
|---|---|---|---|
| 全市场日线 | `pro.daily(trade_date=)` | ✅ 5526 行/次 | `vol`手、`amount`千元 |
| 每日指标 PE/PB/市值/换手/量比 | `pro.daily_basic(trade_date=)` | ✅ 5526 行/次 | `total_mv/circ_mv`万元 |
| 复权因子 | `pro.adj_factor(trade_date=)` | ✅ 5553 行/次 | - |
| 股票列表+行业+上市日 | `pro.stock_basic(list_status=L)` | ✅ 5530 只 | - |
| 涨跌停价 | `pro.stk_limit(trade_date=)` | ✅ 7705 行/次 | - |
| **资金流（全市场）** | `pro.moneyflow(trade_date=)` | ✅ 5198 行/次 | `net_mf_amount`万元 |
| **龙虎榜** | `pro.top_list(trade_date=)` | ✅ 87 行/次 | `net_amount`元 |
| **龙虎榜机构席位** | `pro.top_inst(trade_date=)` | ✅ 949 行/次 | `net_buy`元，`side`0买1卖 |
| 财务三表 | `pro.income/balancesheet/cashflow(ts_code=,period=)` | ✅ **必传 ts_code**，不能按 period 批量 | - |
| 财务指标 | `pro.fina_indicator(ts_code=,period=)` | ✅ 同上 | - |
| 大宗/解禁/股东人数/高管 | `block_trade/share_float/stk_holdernumber/stk_managers` | ✅ | - |
| 指数日线 | `pro.index_daily(ts_code=)` | ✅ | 代码 `000001.SH` 格式 |
| 交易日历 | `pro.trade_cal` | ✅ | - |
| 涨停池细分（打板专题）| `limit_list_d` | ❌ **无权限** | 用 daily+stk_limit 自算替代 |
| 盘中实时快照 | 无（TuShare 是 EOD）| ❌ | 保留东财 clist |
| 分钟线 | 单独购买 | ❌ | 保留 mootdx（如需）|

**关键修正**：用户交接文档说"资金流/龙虎榜是单独权限"，**实测 2000 档均可调通**。仅打板专题 `limit_list_d` 和盘中实时无解。结论：**除盘中实时外，TuShare 几乎能替换所有 EOD 数据**。

### 1.2 现状诊断（代码实测，比 2026-07-23 调研报告新）

- **universe ~2447 只**（07-21 已 backfill，报告测的 100 是更早状态）
- **数据源单一** `AkshareGateway`（东财/腾讯爬虫），无 Protocol/ABC，13 个 service 用 `gateway: Any` 鸭子类型注入
- **回补瓶颈**：`_backfill_bars` **逐只** `fetch_stock_daily_history(adjust="qfq")`，4000 只 × 0.2-0.3s ≈ 60-90 分钟，受 Clash/东财风控
- **资金流**已优化为 `clist` 批量；**龙虎榜**走 `datacenter-web`（不被 Clash 封）
- **选股器**：54 指标 + 8 策略 + 评分模式（all/any/score），指标全向量化 `compute_features`，但偏截面，最复杂仅"近5日金叉"（`tail(5).max()`）
- **涨停判定**用 `change_pct >= 9.8/19.8` 阈值法，对 ST(5%)、近涨停误判
- **启动补偿已禁用**（曾砸 DB），回补只走前端按钮 + 15:40 cron
- **列契约隐式**：个股方法返回中文列、指数方法返回英文列，下游 `_pick_col` 兜底，列名错会**静默丢字段**

### 1.3 三大改造主线

1. **数据源**：TuShare 做 EOD 全量主源（按日期批量，90 分钟 → 10 秒），AKShare 保留盘中实时 + fallback
2. **策略**：引入 MyTT 底座 + 条件树 IR（函数嵌套），对标通达信时序函数（BARSLAST/COUNT/CROSS）
3. **回测**：信号统计法（T+N 胜率）+ TDX 公式 DSL 导入 + 多因子打分

---

## 二、P0 数据源切换（1-2 周）

### 2.1 新增 `TushareGateway` 适配器（`app/tushare_client.py`）

与 `AkshareGateway` **同方法名同返回列**（关键契约），service 零改动即可换注入。

```python
class TushareGateway:
    def __init__(self, token: str) -> None:
        self._pro = ts.pro_api(token)
        self._rate = _RateLimiter(min_interval=0.3)  # 复用现有限流器
        self._source_snapshots: dict[str, dict] = {}

    # 按 trade_date 一次拉全市场（核心质变点）
    def fetch_daily_by_date(self, trade_date: str) -> pd.DataFrame:
        # pro.daily(trade_date=) + pro.adj_factor(trade_date=) + pro.stk_limit(trade_date=)
        # 自算 qfq: qfq_close = close * adj_factor / 最新adj_factor
        # 单位换算：vol×100(股), amount×1000(元)
        # 返回中文列：日期/开盘/收盘/最高/最低/成交量/成交额/涨跌幅/换手率（与 AkshareGateway 一致）

    def fetch_daily_basic_by_date(self, trade_date: str) -> pd.DataFrame:
        # pro.daily_basic(trade_date=) -> PE/PE_TTM/PB/PS/总市值/流通市值/换手率/量比/股息率
        # 单位：total_mv/circ_mv ×10000(元)

    def fetch_fund_flow_by_date(self, trade_date: str) -> pd.DataFrame:
        # pro.moneyflow(trade_date=) -> net_mf_amount(主力净额,×10000元)
        # 超大单净额 = (buy_elg_amount - sell_elg_amount)×10000
        # 大单净额 = (buy_lg_amount - sell_lg_amount)×10000

    def fetch_lhb_by_date(self, trade_date: str) -> pd.DataFrame:
        # pro.top_list(trade_date=) + pro.top_inst(trade_date=)
        # 机构席位：top_inst 按 ts_code group，side='0'买方，count(exalter 含"机构") = 机构买入席位数
        # 机构净席位 = 买入机构席位数 - 卖出机构席位数（比东财"解读"列正则更准）

    # 逐只方法（财务接口必须按 ts_code）：
    def fetch_financial(self, ts_code: str, period: str) -> dict: ...
    def fetch_fina_indicator(self, ts_code: str) -> pd.DataFrame: ...
```

**单位换算清单（适配层统一处理，最易出错点）**：
| 接口 | 字段 | TuShare 单位 | 入库单位 |
|---|---|---|---|
| daily | vol | 手 | 股 ×100 |
| daily | amount | 千元 | 元 ×1000 |
| daily_basic | total_mv/circ_mv | 万元 | 元 ×10000 |
| moneyflow | net_mf_amount/buy_*_amount | 万元 | 元 ×10000 |
| top_list/top_inst | net_amount/net_buy | 元 | 元（直接）|

### 2.2 抽 `MarketDataGateway` Protocol（`app/gateway_protocol.py`）

```python
class MarketDataGateway(Protocol):
    def fetch_stock_daily_history(self, symbol, start, end, adjust="") -> pd.DataFrame: ...
    def fetch_daily_by_date(self, trade_date: str) -> pd.DataFrame: ...  # 新增，TuShare 批量
    def fetch_daily_basic_by_date(self, trade_date: str) -> pd.DataFrame: ...
    def fetch_fund_flow_by_date(self, trade_date: str) -> pd.DataFrame: ...
    def fetch_lhb_by_date(self, trade_date: str) -> pd.DataFrame: ...
    def fetch_individual_realtime(self) -> pd.DataFrame: ...  # 盘中实时，TuShare 无，AKShare 独占
    def fetch_limit_up_pool(self, date: str) -> pd.DataFrame: ...  # 东财4池，TuShare 无
    # ... 每方法文档化返回列契约
```

- `AkshareGateway` 显式 implement（不改行为，仅类型标注）
- `TushareGateway` implement；对 TuShare 无解的方法（盘中实时、涨停4池）`raise NotImplementedError`
- **列契约快照测试**：比对两 gateway 各方法输出列名一致（防 `_pick_col` 静默丢字段）

### 2.3 `CompositeGateway` 双源互备（`app/gateway_composite.py`）

```python
class CompositeGateway:
    """TuShare 主，AKShare 备。主源失败/超时自动降级，记录 source_snapshot。"""
    def __init__(self, primary: TushareGateway, fallback: AkshareGateway): ...
    def fetch_daily_by_date(self, trade_date):
        try: return self.primary.fetch_daily_by_date(trade_date)
        except: self._mark_fallback("daily"); return self._fallback_by_date(trade_date)
    # 盘中实时、涨停4池直接走 fallback（TuShare 无）
```

复用 `AkshareGateway._run` 的 25s 超时壳 + `_set_source_snapshot` 降级标记，前端"数据来源"标签不断。

### 2.4 回补改"按日期批量"（`app/services/daily_bars.py`）

**核心改造**：新增 `backfill_by_date(session, trade_date)`，替代逐只 `_backfill_bars`：

```python
def backfill_by_date(self, session, trade_date: str) -> dict:
    # 1. pro.daily(trade_date) -> 5526 行 -> stock_daily_bars（一次 upsert）
    # 2. pro.adj_factor(trade_date) -> 自算 qfq 复权价更新 close/open/high/low
    # 3. pro.daily_basic(trade_date) -> stock_daily_basic（新表）
    # 4. pro.moneyflow(trade_date) -> stock_fund_flow_daily（替代逐只+clist）
    # 5. pro.stk_limit(trade_date) -> 缓存涨停价用于精确判定
    # 200 行 chunk commit（DB 截断事故硬约定）
    # 耗时：~10 秒（vs 逐只 90 分钟）
```

- 保留 `ensure_recent_bars` 逐只作为 **fallback**（TuShare 全挂时降级到 AKShare 逐只）
- `backfill_all` 改为先尝试 `backfill_by_date`（最近 N 日），失败降级逐只
- 15:40 cron 改调 `backfill_by_date(today)`，历史缺口用 `backfill_by_date` 循环补

### 2.5 universe 改用 `stock_basic` + `daily_basic`（`get_universe`）

```python
def get_universe(self, session, min_amount=50_000_000, as_of=None):
    # 主路径：stock_basic(list_status=L) 全市场 + daily_basic(成交额/换手) 过滤
    # 不再依赖 individual_stock_snapshots（盘中快照表）
    # 历史回放：daily(trade_date).amount 过滤
    # ST 过滤：stock_basic.name 含 ST（TuShare 直接标）
```

### 2.6 新增表（`app/models.py`，schema 改前备份 DB）

| 表 | 来源 | 用途 |
|---|---|---|
| `stock_daily_basic` | daily_basic | PE_TTM/PB/PS/市值/换手/量比/股息率，按 (code,date) |
| `stock_financial` | income/balancesheet/cashflow | 财务三表，按 (code,end_date,report_type)，point-in-time（ann_date 发布日）|
| `stock_fina_indicator` | fina_indicator | ROE/增速/毛利率等，按 (code,end_date) |
| `stk_limit_daily` | stk_limit | 涨跌停价，按 (code,date)，涨停精确判定 |
| `stock_event` | block_trade/share_float/stk_holdernumber | 大宗/解禁/股东人数，事件驱动策略 |

财务接口只能按 ts_code 查，全市场一次性拉 ~5500 只 × 4 表 ≈ 22000 次调用，200 次/分钟 ≈ 2 小时。**每季更新一次**，缓存到 `stock_financial`，按报告期增量。

### 2.7 token 配置 + 依赖

- `app/config.py`：`TUSHARE_TOKEN = os.environ.get("EQ_TUSHARE_TOKEN")`（仿 JWT secret 模式，**不硬编码**）
- `pyproject.toml`：加 `tushare>=1.4.29`、`mytt>=2.0`（P1 用）
- launchd plist 加 `EQ_TUSHARE_TOKEN` 环境变量
- token 已在对话暴露，**上线前建议在 TuShare 后台重置 token**

### 2.8 P0 验收

- 15:40 cron `backfill_by_date` 10 秒内完成全市场日线+资金流+daily_basic 入库
- universe 从 stock_basic 来，≥5000 只
- 选股器用 TuShare 数据跑通现有 8 策略，结果与 AKShare 时期一致或更全
- 双源切换有 source_snapshot 日志，TuShare 挂时自动降级 AKShare
- 全套 pytest pass（含列契约快照测试）

---

## 三、P1 策略专业化核心（3-6 周）

### 3.1 引入 MyTT 底座（`app/services/indicator_engine.py` 新建）

[MyTT](https://github.com/mpquant/MyTT) 是通达信公式的 Python 移植，单文件纯 pandas，提供 `REF/MA/EMA/CROSS/HHV/LLV/COUNT/BARSLAST/EVERY/EXIST/FILTER/SMA/RSI/MACD/KDJ/BOLL/OBV/ATR/BIAS/CCI/DMA/WINNER/COST` 全套，与通达信结果一致到小数点后 2 位。

- 现有 `compute_features` 的 MA/MACD/RSI 逐步迁移到 MyTT（行为不变，可对照回归）
- 新指标直接用 MyTT 函数，零数据成本

### 3.2 指标库扩到 150+（`INDICATOR_REGISTRY`）

| 来源 | 新增指标 | 数量 |
|---|---|---|
| MyTT 时序衍生 | KDJ(K/D/J)、BOLL(上/中/下轨)、OBV、ATR、BIAS多周期、CCI、DMA、WR、SAR | +25 |
| 时序事件派生 | 距上次涨停天数(BARSLAST)、近N日金叉次数(COUNT)、HHV/LLV突破、连续放量/缩量、EVERY/EXIST 形态 | +20 |
| 基本面因子（新表）| ROE、毛利率、净利率、营收增速、扣非净利增速、资产负债率、经营现金流/净利润、PE_TTM、PB、PS、PEG、股息率 | +15 |
| 资金面增强 | 多日资金流趋势、主力净占比、超大单占比、机构席位净额（top_inst）| +10 |
| 事件因子（新表）| 近N日大宗折价、解禁压力、股东人数变化、高管增减持 | +10 |

### 3.3 条件树 IR 升级（核心，`app/services/screener_ir.py` 新建）

**现状**：`{indicator, op, value, weight}`，indicator 必须是具名指标，只能截面比较。
**升级为条件树 IR**：

```python
# 表达式节点
{"type": "indicator", "name": "close"}                      # 具名指标（兼容现有）
{"type": "field", "name": "close"}                          # 原始字段
{"type": "func", "name": "REF", "args": [{"field":"close"}, 5]}      # 函数嵌套
{"type": "func", "name": "BARSLAST", "args": [{"indicator":"limit_up_today"}]}
{"type": "binop", "op": "/", "left": {...}, "right": {...}} # 算术组合

# 条件节点
{"type": "compare", "left": {expr}, "op": ">=", "right": {expr|value}, "weight": 2}
{"type": "and"/"or"/"not", "children": [...]}

# 中间变量（事件锚点）
{"type": "assign", "name": "T", "expr": {"func":"BARSLAST","args":[...]}}
# 后续条件可引用 {"type":"var","name":"T"}
```

**编译器** `compile_ir(ir, bars, fund_flow, basic, lhb) -> pd.Series[bool]`：把 IR 编译成 pandas/MyTT 向量化计算，全市场一次算出布尔 mask。评分模式复用现有 `apply_dsl` 的 weight/min_score 逻辑。

**能表达的通达信公式示例**（报告 6.1.2）：
```
T:=BARSLAST(涨停); XG:T>=3 AND T<=10 AND V<REF(V,T)*0.5 AND L<=REF(C,T)*0.92 AND MA(C,5)>MA(C,10)
```
IR 等价：`assign T = BARSLAST(limit_up_today)` → `compare T >= 3` ∧ `compare T <= 10` ∧ `compare V < REF(V,T)*0.5` ∧ ...

**前端**：ConditionBuilder 升级为"锚点事件 + 相对条件"引导式表单，编译为同一 IR（降低手写 IR 门槛）。

### 3.4 涨停判定精确化

- `compute_features` 的 `is_limit_up` 改用 `stk_limit.up_limit`：`close >= up_limit`（替代 `change_pct >= 9.8` 阈值）
- ST(5%)、创业板/科创板(20%)、主板(10%) 全板块精确
- 连板数：`daily` 连续 N 日 `close >= up_limit` 自算（`limit_list_d` 无权限的替代方案）
- `sealed_amount`（封单金额）TuShare 2000 档无（`limit_list_d.fd_amount` 才有）→ 保留东财涨停池源，或降级为 nullable

### 3.5 策略库升级（`BUILTIN_PRESETS`，8 改进 + 新增）

**现有 8 策略改进**（按报告 6.4.1）：
- 放量突破：加平台长度 + 换手率过滤（N日新高+倍量+阳线三要素）
- 缩量回踩：改 BARSLAST 锚定最近涨停/突破日，回踩相对锚点量价
- 趋势多头：加 `MA5>REF(MA5,1)` 向上发散 + EVERY 持续 N 日
- 主力抢筹：加多日净流入趋势 + 机构席位交叉验证（top_inst），UI 标注口径
- 龙虎榜接力：加机构席位净额（top_inst 重建）、上榜原因分类、次日竞价量能
- 涨停接力：加同板块连板梯队、首板/一进二位置

**新增策略**（报告 6.4.2 + 附录A）：
| 策略 | 通达信公式 | 类别 |
|---|---|---|
| 涨停后缩量回踩 | `T:=BARSLAST(涨停); T>=3 AND T<=10 AND V<REF(V,T)*0.5 AND L<=REF(C,T)*0.92 AND MA(C,5)>MA(C,10)` | 形态 |
| N字涨停 | `T:=BARSLAST(涨停); BETWEEN(T,2,10) AND 涨停 AND C>REF(HHV(H,T+1),1)` | 事件 |
| MACD零上二次金叉 | `JCC:=CROSS(DIF,DEA); JCC AND COUNT(JCC,20)=2 AND DEA>0` | 趋势 |
| 龙回头 | 强势股回踩不破涨停实体中位、企稳放量阳突破 | 形态 |
| 回踩20日线不破 | `EXIST(CROSS(C,MA(C,20)),3) AND COUNT(V<REF(V,1),2)>=1 AND C>MA(C,20)` | 趋势 |
| 低估成长组合 | `PE_TTM<30 AND ROE>15 AND 近3年净利复合增速>20 AND 非ST` | 基本面 |
| 多因子打分TopN | 估值+动量+质量等权打分取 Top20，月调仓 | 多因子 |

策略库达 15+，覆盖趋势/动量/量价/形态/事件/基本面/资金/多因子。

### 3.6 信号统计法回测（`app/services/backtest.py` 新建）

对每个历史交易日执行 IR，统计入选股 T+1/T+3/T+5/T+10/T+20 收益分布、胜率、平均超额（对沪深300 + 所属行业指数）。

**新表**：
- `screen_run`：run_id、策略ID/IR 快照、选股日期、universe 版本、数据快照版本、命中数
- `screen_result`：run_id、股票代码、各子条件命中明细、因子值快照、得分

**避坑**：前复权收益、涨跌停不可成交（下一可成交价）、幸存者偏差（universe 按日快照含退市股）、交易成本（万2.5佣金+千0.5印花税+滑点）。

**前端**：策略卡片展示"T+N 胜率与超额"，替代现有"近5日命中数"。

### 3.7 P1 验收

- 涨停后缩量回踩公式可配置运行（BARSLAST 锚点）
- 指标库 ≥150，含 KDJ/BOLL/OBV/基本面因子
- 策略卡片展示 T+N 胜率与超额
- IR 编译器单元测试覆盖全部函数节点 + 未来函数检测
- MyTT 迁移后 MA/MACD/RSI 与旧实现数值回归一致

---

## 四、P2 差异化能力（2-3 月）

### 4.1 TDX DSL 解析器（`app/services/tdx_parser.py` 新建）

用 `lark` 解析通达信公式文本 → AST → 生成 IR → 复用 P1 IR 引擎。语法转换仅三处：`:=`→赋值、`AND`→`&`、`OR`→`|`。支持"粘贴通达信公式直接选股"。

### 4.2 未来函数检测

IR 校验时对 `BACKSET/ZIG/PEAK/TROUGH/REFX` 类函数直接拒绝或强警告（检验标准：信号出现后不随后续 K 线改变）。

### 4.3 多因子打分模型（报告 6.3.2 七步）

股票池过滤 → 候选因子 → 预处理（缩尾 0.5%/99.5% + Z-score + 行业市值中性化）→ IC/ICIR 有效性检验 → IC 加权合成 → TopN 调仓 → 样本外验证。

### 4.4 选股流水线

选股结果可存为板块（股票池），板块可作为下一次筛选或预警的输入，形成可组合流水线（对标通达信 tpool）。

### 4.5 盘中实时预警（依赖 P0 保留的东财 clist）

push2 轮询全市场快照 + IR 增量触发 + 推送，延迟 <1 分钟。

---

## 五、实施路线图

| 阶段 | 周期 | 任务 | 验收 |
|---|---|---|---|
| **P0** | 1-2 周 | TushareGateway + Protocol + CompositeGateway + 按日期批量回补 + 新表 + universe 改造 | 15:40 cron 10 秒回补全市场；8 策略跑通；双源互备 |
| **P1** | 3-6 周 | MyTT 底座 + 指标库 150+ + 条件树 IR + 涨停精确化 + 策略库 15+ + 信号统计回测 | 涨停后缩量回踩可配置；策略卡 T+N 胜率 |
| **P2** | 2-3 月 | TDX DSL + 未来函数检测 + 多因子打分 + 选股流水线 + 盘中预警 | 粘贴通达信公式直接选股；预警延迟<1分钟 |

**建议交付节奏**：P0 先独立上线（数据源切换见效快、风险低），验证稳定后再做 P1，P2 视优先级排期。每个阶段开独立子分支 + 完整测试 + 部署上线（遵循 [[project-easyquant-delivery-workflow]]）。

---

## 六、风险与回退

| 风险 | 缓解 |
|---|---|
| **DB 截断事故重演**（[[incident-2026-07-21-screener-backfill-truncated-db]]）| 200 行 chunk commit；不写启动补偿；测试绝不 `import app.main`；脚本只读连接 |
| **列契约静默丢字段** | 列契约快照测试比对两 gateway 输出；适配层单位换算单测覆盖 |
| **TuShare 宕机**（2025-08 曾停一周）| CompositeGateway 双源互备，TuShare 挂自动降级 AKShare |
| **Clash 封 push2** | TuShare 走 tushare.pro 域名，不走 push2/push2his，规避；盘中实时保留东财 clist（已验证 datacenter 不被封）|
| **单位换算错** | 适配层集中处理 + 单测；moneyflow/市值 ×10000、amount ×1000、vol ×100 |
| **财务接口逐只慢** | 每季增量更新；按 universe 分批；200 次/分钟限流 |
| **token 暴露** | 走 `EQ_TUSHARE_TOKEN` 环境变量，不硬编码；上线前重置 |
| **回退** | P0 纯新增（新 gateway/新表），回退 = 切回 AKShareGateway 注入 + 不调 backfill_by_date；P1 IR 与现有 DSL 并存，旧策略不动 |

---

## 七、测试策略

- **数据源层**：`tests/test_tushare_gateway.py`（mock SDK + 单位换算 + 列契约）、`tests/test_composite_gateway.py`（降级切换）
- **回补**：`tests/test_daily_bars_backfill_by_date.py`（in-memory SQLite + FakeGateway，200 行 chunk 守护）
- **IR 引擎**：`tests/test_screener_ir.py`（全函数节点 + 未来函数检测 + BARSLAST 锚点用例）
- **MyTT 迁移**：`tests/test_indicator_regression.py`（MA/MACD/RSI 新旧实现数值一致）
- **回测**：`tests/test_backtest.py`（合成 K 线 + 已知胜率 + 涨跌停不可成交）
- 全套 `uv run pytest tests/ -q` pass；前端 `npm run build:spa`
- 真实数据冒烟：`backfill_by_date(today)` → 跑"涨停后缩量回踩" → 检查结果合理性

---

## 八、附录：TuShare 接口 ↔ 现有方法映射

| 现有 AkshareGateway 方法 | TuShare 替代 | 备注 |
|---|---|---|
| `fetch_stock_daily_history`（逐只）| `daily(trade_date)` + `adj_factor`（按日期批量）| 90 分钟 → 10 秒 |
| `fetch_individual_realtime`（EOD 部分）| `daily` + `daily_basic` | 盘中实时仍走东财 clist |
| `fetch_stock_fund_flow_history`（逐只）| `moneyflow(trade_date)`（批量）| 主力净额 net_mf_amount |
| `fetch_fund_flow_today_batch` | `moneyflow(trade_date)` | 替代 clist |
| `fetch_lhb_detail` | `top_list` + `top_inst` | 机构席位更准（按 side 统计）|
| `fetch_limit_up_pool`（4 池）| `limit_list_d` ❌无权限 | 保留东财 / daily+stk_limit 自算连板 |
| `fetch_market_index_history` | `index_daily` | 代码 `000001.SH` 格式 |
| `fetch_market_index_spot`（实时）| 无 | 保留腾讯 |
| 新增 | `daily_basic` / `income` / `fina_indicator` / `stk_limit` / `block_trade` 等 | 基本面+事件新能力 |
