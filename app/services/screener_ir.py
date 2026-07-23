"""条件树 IR 引擎（P1-2）：对标通达信时序函数。

让选股器表达"涨停后 3-10 天内缩量回踩"这类"事件锚点 + 相对取值"逻辑，突破
现有 ``{indicator, op, value}`` 截面比较的限制（无法表达 BARSLAST(涨停) + REF(V,T)）。

IR 节点（JSON，前端友好）：
  表达式 expr：
    {"type":"const","value":3}
    {"type":"indicator","name":"close_vs_ma20"}   # 取 frame 列（latest 值）
    {"type":"field","name":"close"}                # 取 bars latest 行
    {"type":"var","name":"T"}                      # 中间变量
    {"type":"func","name":"BARSLAST","args":[cond]}
    {"type":"binop","op":"*","left":expr,"right":expr}
  条件 cond：
    {"type":"compare","left":expr,"op":">=","right":expr}
    {"type":"and"/"or","children":[cond,...]}
    {"type":"not","child":cond}
  赋值：
    {"vars":[{"name":"T","expr":expr},...],"root":cond}

时序函数（在 bars 全序列上算，返回 latest 行对齐 frame）：
  REF(X,N) / MA(X,N) / EMA / HHV / LLV / COUNT(cond,N) / BARSLAST(cond) /
  CROSS(A,B) / EVERY(cond,N) / EXIST(cond,N)

设计要点：
- 两套求值：``_eval_expr`` 返回 latest Series（每股一个值）；``_series`` 返回 bars
  完整序列（时序函数参数）。indicator 只有 latest 值，不能做 REF 参数（用 field 替代）。
- 未来函数检测：BACKSET/ZIG/PEAK/TROUGH/REFX 直接拒绝（回测会系统性高估胜率）。
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 未来函数黑名单（信号随后续 K 线改变，回测胜率虚高）
_FUTURE_FUNCTIONS = {"BACKSET", "ZIG", "PEAKA", "PEAK", "TROUGHA", "TROUGH", "REFX"}

# 支持的时序函数
_SUPPORTED_FUNCS = {"REF", "MA", "EMA", "HHV", "LLV", "COUNT", "BARSLAST", "CROSS", "EVERY", "EXIST", "LAST"}


class IRError(Exception):
    """IR 编译/求值错误。"""


def check_future_functions(ir: dict) -> list[str]:
    """递归检测 IR 中的未来函数，返回违规函数名列表。"""
    found: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "func":
                fn = str(node.get("name", "")).upper()
                if fn in _FUTURE_FUNCTIONS:
                    found.append(fn)
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(ir)
    return found


class IREvaluator:
    """条件树 IR 求值器。

    ``bars``：120 日日线（stock_code/trading_date/open/close/high/low/volume/amount/...）。
    ``frame``：latest 特征帧（每股一行，含 INDICATOR_REGISTRY 指标列 + stock_code）。
    """

    def __init__(self, bars: pd.DataFrame, frame: pd.DataFrame, fund_flow: pd.DataFrame | None = None) -> None:
        self.bars = bars
        self.frame = frame
        self.fund_flow = fund_flow or pd.DataFrame()
        self.vars: dict[str, pd.Series] = {}
        if not bars.empty:
            self._grouped = bars.groupby("stock_code", sort=False)
            self._tail1 = bars.groupby("stock_code").tail(1).set_index("stock_code")
        else:
            self._grouped = None
            self._tail1 = pd.DataFrame()

    def evaluate(self, ir: dict) -> pd.Series:
        """求值 IR -> 布尔 Series（index 对齐 frame）。"""
        future = check_future_functions(ir)
        if future:
            raise IRError(f"IR 含未来函数 {future}，拒绝求值（回测会系统性高估）")
        for var in ir.get("vars", []):
            self.vars[var["name"]] = self._eval_expr(var["expr"])
        return self._eval_condition(ir["root"])

    # ---------------- 表达式（latest Series，对齐 frame） ----------------

    def _eval_expr(self, expr: dict) -> pd.Series:
        t = expr.get("type")
        if t == "const":
            return pd.Series(float(expr["value"]), index=self.frame.index)
        if t == "indicator":
            name = expr["name"]
            if name in self.frame.columns:
                return pd.to_numeric(self.frame[name], errors="coerce")
            raise IRError(f"indicator '{name}' 不在 frame 列中")
        if t == "field":
            name = expr["name"]
            if name in self._tail1.columns:
                return self.frame["stock_code"].map(self._tail1[name]).astype(float)
            raise IRError(f"field '{name}' 不在 bars 列中")
        if t == "var":
            if expr["name"] in self.vars:
                return self.vars[expr["name"]]
            raise IRError(f"未定义变量 '{expr['name']}'")
        if t == "func":
            return self._eval_func(expr.get("name", "").upper(), expr.get("args", []))
        if t == "binop":
            left = self._eval_expr(expr["left"])
            right = self._eval_expr(expr["right"])
            return self._binop(left, expr["op"], right)
        raise IRError(f"未知表达式类型: {t}")

    def _eval_func(self, name: str, args: list[dict]) -> pd.Series:
        if name not in _SUPPORTED_FUNCS:
            raise IRError(f"不支持的函数: {name}")
        if name == "CROSS":
            return self._latest_of(self._cross_series(args))
        if name in ("COUNT", "BARSLAST", "EVERY", "EXIST", "LAST"):
            cond = self._eval_condition_bars(args[0])
            n = int(self._const_value(args[1])) if len(args) > 1 else 1
            return self._latest_of(self._apply_seq_func(name, cond, n))
        # REF 支持 var N（如 REF(volume, BARSLAST(涨停))）；MA/EMA/HHV/LLV 的 N 必须是 const
        if name == "REF":
            x = self._series(args[0])
            n_expr = args[1]
            if n_expr.get("type") == "const":
                return self._latest_of(x.groupby(self.bars["stock_code"]).shift(int(n_expr["value"])))
            # var/expr N：每股取其 N 天前的值（BARSLAST 锚点回溯）
            n_series = self._eval_expr(n_expr)
            return self._ref_var(x, n_series)
        # MA/EMA/HHV/LLV
        x = self._series(args[0])
        n = int(self._const_value(args[1]))
        return self._latest_of(self._apply_window_func(name, x, n))

    # ---------------- 序列（bars 完整时序，用于时序函数参数） ----------------

    def _series(self, expr: dict) -> pd.Series:
        t = expr.get("type")
        if t == "field":
            if expr["name"] in self.bars.columns:
                return pd.to_numeric(self.bars[expr["name"]], errors="coerce")
            raise IRError(f"field '{expr['name']}' 不在 bars 列中")
        if t == "indicator":
            return self._indicator_series(expr["name"])
        if t == "func":
            return self._func_series(expr.get("name", "").upper(), expr.get("args", []))
        if t == "binop":
            left = self._series(expr["left"])
            right = self._series(expr["right"])
            return self._binop(left, expr["op"], right)
        if t == "const":
            return pd.Series(float(expr["value"]), index=self.bars.index)
        if t == "var":
            # var 是 latest Series，广播到 bars（每组 latest 值填到该组所有行）
            latest = self.vars[expr["name"]]
            return self.bars["stock_code"].map(latest.set_index(self.frame["stock_code"])).astype(float)
        raise IRError(f"无法取序列: {t}")

    def _indicator_series(self, name: str) -> pd.Series:
        """indicator 的历史序列（REF/MA 参数）。支持基本字段 + MA。"""
        if name in self.bars.columns:
            return pd.to_numeric(self.bars[name], errors="coerce")
        g = self._grouped
        if name in ("ma5", "ma10", "ma20", "ma60"):
            n = int(name[2:])
            return g["close"].transform(lambda s, n=n: s.rolling(n, min_periods=n).mean())
        raise IRError(f"indicator '{name}' 无历史序列实现（REF/MA 仅支持 bars 字段 + ma5/10/20/60）")

    def _func_series(self, name: str, args: list[dict]) -> pd.Series:
        if name in ("REF", "MA", "EMA", "HHV", "LLV"):
            x = self._series(args[0])
            n = int(self._const_value(args[1]))
            return self._apply_window_func(name, x, n)
        if name in ("COUNT", "BARSLAST", "EVERY", "EXIST", "LAST"):
            cond = self._eval_condition_bars(args[0])
            n = int(self._const_value(args[1])) if len(args) > 1 else 1
            return self._apply_seq_func(name, cond, n)
        if name == "CROSS":
            return self._cross_series(args)
        raise IRError(f"无序列实现的函数: {name}")

    def _apply_window_func(self, name: str, x: pd.Series, n: int) -> pd.Series:
        g = self.bars["stock_code"]
        if name == "REF":
            return x.groupby(g).shift(n)
        if name == "MA":
            return x.groupby(g).transform(lambda s: s.rolling(n, min_periods=n).mean())
        if name == "EMA":
            return x.groupby(g).transform(lambda s: s.ewm(span=n, adjust=False).mean())
        if name == "HHV":
            return x.groupby(g).transform(lambda s: s.rolling(n, min_periods=n).max())
        if name == "LLV":
            return x.groupby(g).transform(lambda s: s.rolling(n, min_periods=n).min())
        raise IRError(f"未知窗口函数: {name}")

    def _apply_seq_func(self, name: str, cond: pd.Series, n: int) -> pd.Series:
        g = self.bars["stock_code"]
        c = cond.astype(float)
        if name == "COUNT":
            return c.groupby(g).transform(lambda s: s.rolling(n, min_periods=n).sum())
        if name in ("EVERY", "LAST"):
            return c.groupby(g).transform(lambda s: s.rolling(n, min_periods=n).min())
        if name == "EXIST":
            return c.groupby(g).transform(lambda s: s.rolling(n, min_periods=n).max())
        if name == "BARSLAST":
            def _bl(s: pd.Series) -> pd.Series:
                res = np.full(len(s), np.nan)
                last_true = -1
                for i in range(len(s)):
                    if s.iloc[i]:
                        last_true = i
                    if last_true >= 0:
                        res[i] = i - last_true
                return pd.Series(res, index=s.index)
            return c.groupby(g).transform(_bl)
        raise IRError(f"未知序列函数: {name}")

    def _cross_series(self, args: list[dict]) -> pd.Series:
        a = self._series(args[0])
        b = self._series(args[1])
        g = self.bars["stock_code"]
        a_prev = a.groupby(g).shift(1)
        b_prev = b.groupby(g).shift(1)
        return ((a > b) & (a_prev <= b_prev)).astype(float)

    # ---------------- 条件 ----------------

    def _eval_condition(self, node: dict) -> pd.Series:
        """条件 -> latest bool Series（对齐 frame）。"""
        t = node.get("type")
        if t == "compare":
            left = self._eval_expr(node["left"])
            right = self._eval_expr(node["right"])
            return self._compare(left, node["op"], right)
        if t == "and":
            masks = [self._eval_condition(c) for c in node["children"]]
            return masks[0] if len(masks) == 1 else _reduce(masks, lambda a, b: a & b)
        if t == "or":
            masks = [self._eval_condition(c) for c in node["children"]]
            return masks[0] if len(masks) == 1 else _reduce(masks, lambda a, b: a | b)
        if t == "not":
            return ~self._eval_condition(node["child"])
        # 简写：单个 expr 作为条件（非零为真）
        return self._eval_expr(node) != 0

    def _eval_condition_bars(self, node: dict) -> pd.Series:
        """条件 -> bars bool Series（用于 COUNT/BARSLAST 参数）。"""
        t = node.get("type")
        if t == "compare":
            left = self._series_or_const(node["left"])
            right = self._series_or_const(node["right"])
            return self._compare(left, node["op"], right)
        if t == "and":
            masks = [self._eval_condition_bars(c) for c in node["children"]]
            return masks[0] if len(masks) == 1 else _reduce(masks, lambda a, b: a & b)
        if t == "or":
            masks = [self._eval_condition_bars(c) for c in node["children"]]
            return masks[0] if len(masks) == 1 else _reduce(masks, lambda a, b: a | b)
        if t == "not":
            return ~self._eval_condition_bars(node["child"])
        if t == "func" and node.get("name", "").upper() == "CROSS":
            return self._cross_series(node["args"]).astype(bool)
        if t in ("indicator", "field", "func", "binop"):
            return self._series(node) != 0
        return pd.Series(False, index=self.bars.index)

    def _series_or_const(self, expr: dict) -> pd.Series:
        if expr.get("type") == "const":
            return pd.Series(float(expr["value"]), index=self.bars.index)
        return self._series(expr)

    def _compare(self, left: pd.Series, op: str, right: Any) -> pd.Series:
        if op == "between":
            lo, hi = float(right[0]), float(right[1])
            return left.between(lo, hi)
        if op == ">":
            return left > right
        if op == ">=":
            return left >= right
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        raise IRError(f"未知 op: {op}")

    def _binop(self, left: pd.Series, op: str, right: pd.Series) -> pd.Series:
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            return left / right.replace(0, np.nan)
        raise IRError(f"未知 binop: {op}")

    # ---------------- 工具 ----------------

    def _const_value(self, expr: dict) -> float:
        if expr.get("type") == "const":
            return float(expr["value"])
        raise IRError(f"期望常量参数，得到 {expr.get('type')}（时序函数 N 必须是常量）")

    def _latest_of(self, series: pd.Series) -> pd.Series:
        """bars 序列 -> latest Series（对齐 frame by stock_code）。"""
        tail = series.groupby(self.bars["stock_code"]).tail(1)
        codes = self.bars.groupby("stock_code").tail(1)["stock_code"].values
        s = pd.Series(tail.values, index=codes)
        return self.frame["stock_code"].map(s)

    def _ref_var(self, x: pd.Series, n_series: pd.Series) -> pd.Series:
        """REF(X, varN)：每股取其 N 天前的 X 值（N 每股不同，如 BARSLAST 结果）。

        锚点策略核心：``T:=BARSLAST(涨停); REF(volume, T)`` 取涨停当日成交量。
        O(股票数) 循环，5526 只 <1s。
        """
        result = pd.Series(np.nan, index=self.frame.index, dtype=float)
        codes = self.bars["stock_code"].values
        for i, code in enumerate(self.frame["stock_code"]):
            n = n_series.iloc[i]
            if pd.isna(n) or n < 0:
                continue
            n_int = int(n)
            group_x = x[codes == code]
            if len(group_x) > n_int:
                result.iloc[i] = group_x.iloc[-(n_int + 1)]
        return result


def _reduce(items: list[pd.Series], op) -> pd.Series:
    result = items[0]
    for m in items[1:]:
        result = op(result, m)
    return result


def evaluate_ir(ir: dict, bars: pd.DataFrame, frame: pd.DataFrame, fund_flow: pd.DataFrame | None = None) -> pd.Series:
    """便捷接口：求值 IR -> 布尔 Series（对齐 frame）。"""
    return IREvaluator(bars, frame, fund_flow).evaluate(ir)
