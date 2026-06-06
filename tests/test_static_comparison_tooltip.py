from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parents[1] / "app" / "static"


def test_comparison_chart_tooltip_uses_shared_value_formatter():
    script = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert 'tooltip: {' in script
    assert 'trigger: "axis"' in script
    assert 'return state.metric === "net_strength" ? `${(Number(value) * 100).toFixed(2)}%` : formatAmount(value);' in script
    assert 'comparisonChart.setOption(' in script


def test_comparison_chart_tooltip_sorts_hover_rows_descending():
    script = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert "function sortTooltipParamsDescending(params)" in script
    assert ".slice()" in script
    assert ".sort((left, right) => {" in script
    assert "const leftValue = toNumeric(left?.value);" in script
    assert "const rightValue = toNumeric(right?.value);" in script
    assert "return rightValue - leftValue;" in script
    assert "const ordered = sortTooltipParamsDescending(params);" in script
