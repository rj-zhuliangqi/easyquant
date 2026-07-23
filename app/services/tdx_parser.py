"""TDX DSL 解析器（P2-1）：通达信公式文本 -> 条件树 IR。

让用户"粘贴通达信公式直接选股"--同类 Web 产品中没有的差异化能力。解析后复用
P1-2 的 ``screener_ir.IREvaluator`` 求值，与 IR 策略共用同一套时序函数引擎。

语法转换（通达信 -> IR）：
  ``T:=expr;``       -> vars 赋值
  ``XG:expr;``       -> root 输出
  ``AND``/``&``      -> and
  ``OR``/``|``       -> or
  ``NOT``/``!``      -> not
  ``> >= < <= = !=`` -> compare（``=`` 转 ``==``）
  ``+ - * /``        -> binop
  ``REF/MA/EMA/SMA/HHV/LLV/COUNT/BARSLAST/CROSS/EVERY/EXIST`` -> func
  ``BETWEEN(X,a,b)`` -> X>=a AND X<=b
  ``C/O/H/L/V/AMOUNT/CHANGE_PCT/TURNOVER`` -> field（close/open/high/low/volume/...）

示例：
  ``T:=BARSLAST(CHANGE_PCT>=9.8); XG:T>=3 AND T<=10 AND V<REF(V,T)*0.5 AND L<=REF(C,T)*0.92;``
  等价于 IR 策略"涨停后缩量回踩"。
"""

from __future__ import annotations

import logging
from typing import Any

from lark import Lark, Transformer
from lark.exceptions import VisitError

from app.services.screener_ir import check_future_functions

logger = logging.getLogger(__name__)


class TdxError(Exception):
    """通达信公式解析/转换错误。"""


# 通达信字段名 -> IR field 名
FIELD_MAP = {
    "C": "close", "CLOSE": "close",
    "O": "open", "OPEN": "open",
    "H": "high", "HIGH": "high",
    "L": "low", "LOW": "low",
    "V": "volume", "VOL": "volume", "VOLUME": "volume",
    "AMOUNT": "amount",
    "CHANGE_PCT": "change_pct", "CHANGE": "change_pct",
    "TURNOVER": "turnover_rate",
}


GRAMMAR = r"""
start: stmt+
?stmt: assign | output | bare_output
assign: CNAME ":=" expr ";"
output: CNAME ":" expr ";"
bare_output: expr ";"
?expr: or_expr
?or_expr: or_expr ("OR"|"or"|"|") and_expr -> or_
        | and_expr
?and_expr: and_expr ("AND"|"and"|"&") not_expr -> and_
         | not_expr
?not_expr: ("NOT"|"not"|"!") not_expr -> not_
         | compare
?compare: add_expr CMP_OP add_expr -> compare
        | add_expr
?add_expr: add_expr "+" mul_expr -> add
         | add_expr "-" mul_expr -> sub
         | mul_expr
?mul_expr: mul_expr "*" unary -> mul
         | mul_expr "/" unary -> div
         | unary
?unary: "-" unary -> neg
      | atom
?atom: NUMBER -> number
     | func_call
     | field
     | "(" expr ")"
func_call: CNAME "(" [args] ")"
args: expr ("," expr)*
field: CNAME
CMP_OP: ">=" | "<=" | "!=" | ">" | "<" | "="
CNAME: /[A-Za-z_一-龥][A-Za-z0-9_一-龥]*/
NUMBER: /[0-9]+(\.[0-9]+)?/
%import common.WS
%ignore WS
"""


class TdxToIR(Transformer):
    """AST -> IR dict。"""

    def start(self, items):
        vars_: list[dict] = []
        root: dict | None = None
        for stmt in items:
            if stmt["type"] == "assign":
                vars_.append({"name": stmt["name"], "expr": stmt["expr"]})
            else:  # output
                root = stmt["expr"]
        if root is None:
            raise TdxError("通达信公式无输出语句（需 NAME:expr; 或裸 expr; 输出）")
        return {"vars": vars_, "root": root}

    def assign(self, items):
        return {"type": "assign", "name": str(items[0]), "expr": items[1]}

    def output(self, items):
        return {"type": "output", "name": str(items[0]), "expr": items[1]}

    def bare_output(self, items):
        # 裸表达式输出（无 NAME: 前缀，如 ``CROSS(K,D) AND K<30;``）-> 隐式 XG 输出
        return {"type": "output", "name": "XG", "expr": items[0]}

    def or_(self, items):
        left, right = items[0], items[1]
        # 左递归链式 a OR b OR c -> 扁平化 [a, b, c]
        if isinstance(left, dict) and left.get("type") == "or":
            return {"type": "or", "children": left["children"] + [right]}
        return {"type": "or", "children": [left, right]}

    def and_(self, items):
        left, right = items[0], items[1]
        if isinstance(left, dict) and left.get("type") == "and":
            return {"type": "and", "children": left["children"] + [right]}
        return {"type": "and", "children": [left, right]}

    def not_(self, items):
        return {"type": "not", "child": items[0]}

    def compare(self, items):
        op = str(items[1])
        if op == "=":
            op = "=="
        return {"type": "compare", "left": items[0], "op": op, "right": items[2]}

    def add(self, items):
        return {"type": "binop", "op": "+", "left": items[0], "right": items[1]}

    def sub(self, items):
        return {"type": "binop", "op": "-", "left": items[0], "right": items[1]}

    def mul(self, items):
        return {"type": "binop", "op": "*", "left": items[0], "right": items[1]}

    def div(self, items):
        return {"type": "binop", "op": "/", "left": items[0], "right": items[1]}

    def neg(self, items):
        return {"type": "binop", "op": "*", "left": {"type": "const", "value": -1.0}, "right": items[0]}

    def number(self, items):
        return {"type": "const", "value": float(items[0])}

    def field(self, items):
        raw = str(items[0])
        if raw.upper() in FIELD_MAP:
            return {"type": "field", "name": FIELD_MAP[raw.upper()]}
        # 变量名或未知字段：保留原样，后处理时引用 assign 变量的转 var
        return {"type": "field", "name": raw}

    def func_call(self, items):
        fname = str(items[0]).upper()
        args = items[1] if len(items) > 1 and isinstance(items[1], list) else []
        # BETWEEN(X, a, b) -> X>=a AND X<=b
        if fname == "BETWEEN" and len(args) == 3:
            return {"type": "and", "children": [
                {"type": "compare", "left": args[0], "op": ">=", "right": args[1]},
                {"type": "compare", "left": args[0], "op": "<=", "right": args[2]},
            ]}
        return {"type": "func", "name": fname, "args": args}

    def args(self, items):
        return list(items)


_parser = Lark(GRAMMAR, parser="lalr", start="start")


def _field_to_var(node: Any, var_names: set[str]) -> None:
    """递归把引用 assign 变量名的 field 节点转 var 节点（in-place）。

    通达信公式里 ``T:=...; XG:T>=3`` 的 T 是变量，但词法上 T 与字段一样都是 CNAME，
    解析为 field；此处根据 vars 名字集合把引用变量的 field 改成 var。
    """
    if not isinstance(node, dict):
        return
    if node.get("type") == "field" and node.get("name") in var_names:
        node["type"] = "var"
    for v in node.values():
        if isinstance(v, dict):
            _field_to_var(v, var_names)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    _field_to_var(item, var_names)


def parse_tdx(text: str) -> dict[str, Any]:
    """通达信公式文本 -> IR dict（复用 ``screener_ir.evaluate_ir`` 求值）。

    抛 ``TdxError``：语法错误 / 无输出语句 / 含未来函数。
    """
    if not text or not text.strip():
        raise TdxError("公式为空")
    try:
        tree = _parser.parse(text)
    except Exception as exc:  # noqa: BLE001
        raise TdxError(f"通达信公式解析失败：{exc}") from exc
    try:
        ir = TdxToIR().transform(tree)
    except VisitError as ve:
        if isinstance(ve.orig_exc, TdxError):
            raise ve.orig_exc
        raise TdxError(f"通达信公式转换失败：{ve.orig_exc}") from ve
    # 后处理：引用 assign 变量名的 field 转 var 节点
    var_names = {v["name"] for v in ir.get("vars", [])}
    if var_names:
        _field_to_var(ir["root"], var_names)
        for v in ir["vars"]:
            _field_to_var(v["expr"], var_names)
    future = check_future_functions(ir)
    if future:
        raise TdxError(f"公式含未来函数 {future}，拒绝（回测会系统性高估）")
    return ir
