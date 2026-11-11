import numpy as np
import pytest

from graph_analyzer.math_engine import analyze
from graph_analyzer.parser import parse_text


@pytest.mark.parametrize("formula", [
    "x", "x^2", "x**2", "2*x+3", "3x+5", "2sin(x)+cos(x)", "sqrt(x)", "abs(x)",
    "1/x", "sin(x)", "cos(x)", "tan(x)", "cot(x)", "sec(x)", "csc(x)",
    "2sin(x)+3cos(x)", "sin(2x)", "sin(x)^2", "sin^2(x)", "ln(x)", "log(x)",
    "log10(x)", "log2(x)", "e^x", "exp(x)", "2^x", "ln(x+3)", "log(x^2+1)",
    "sqrt(x^2+1)", "cbrt(x)", "abs(x-2)", "floor(x)", "ceil(x)", "round(x)",
    "1/(x-2)", "(x^2+1)/(x-3)", "(2x+1)^3", "2(x+1)", "(x+1)(x-1)",
    "x(x+2)", "2pi", "3e^x", "x^2sin(x)", "2xsin(x)", "sqrt(abs(x))",
    "x/3", "(x-1)^2", "sin(x)+cos(x)", "exp(-x^2)", "1e-3*x",
])
def test_supported_formulas_evaluate(formula):
    expr = parse_text(formula).expressions[0]
    result = analyze(expr, -2, 2, samples=41)
    assert result["x"].size == 41
    assert result["valid"].any()


@pytest.mark.parametrize("restriction", [
    "x < -1", "x > -1", "x <= -1", "x >= -1", "x != 0", "-5 < x < 5",
    "-1 <= x <= 2", "-2pi <= x <= 2pi", "-pi <= x <= pi", "x <= -2 or x >= 2",
    "x < 0 or x > 1", "x >= 0 and x <= 2", "x<2", "x>2", "x<=2", "x>=2",
    "-3 <= x < 4", "-3 < x <= 4", "x != 2", "x < pi", "x > -pi", "x >= 0",
    "x <= 0", "-2 < x < 2", "-2 <= x <= 2", "-2pi<x<2pi", "x< -2 or x>2",
    "x >= -1 and x < 1", "x != -1", "x != pi",
])
def test_domain_filters_samples(restriction):
    expr = parse_text(f"x^2 {{{restriction}}}").expressions[0]
    result = analyze(expr, -4, 4, samples=81)
    assert result["valid"].any()
    assert np.isfinite(result["y"][result["valid"]]).all()


@pytest.mark.parametrize("source,count", [
    ("y=x\ny=2x", 2), ("y1=x\ny2=x^2", 2), ("f(x)=x\ng(x)=x^2", 2),
    ("x;x^2", 2), ("x, y=x^2", 2), ("y=x\ny=sin(x)\ny=cos(x)", 3),
    ("y1=x^2\ny2=2*x+3\ny3=-x+5", 3),
    ("y=x^2+2 {x<-1}\ny=sin(x) {-1<=x<=2}\ny=ln(x+3) {x>2}", 3),
    ("x\nx^2\nx^3", 3), ("x;x^2;x^3", 3), ("y=x, y=x^2, y=x^3", 3),
    ("f(x)=x;g(x)=x^2", 2), ("y1=x;y2=x^2", 2), ("x\n2x\n3x", 3),
    ("sin(x)\ncos(x)", 2), ("ln(x)\nlog(x)", 2),
    ("y=x^2\ny=sin(x)", 2), ("y=x^2; y=sin(x)", 2),
    ("f(x)=x^2\ng(x)=sin(x)\nh(x)=ln(x)", 3), ("y1=x\ny2=x+1\ny3=x+2", 3),
])
def test_multiple_equations_are_independent(source, count):
    parsed = parse_text(source)
    assert len(parsed.expressions) == count
    assert len(parsed.labels) == count


@pytest.mark.parametrize("formula", [
    "2x", "3sin(x)", "2cos(x)", "2(x+1)", "(x+1)(x-1)", "x(x+2)",
    "2pi", "3e^x", "x^2sin(x)", "2xsin(x)", "2cos(2x)", "4tan(x)",
    "5sqrt(x)", "2ln(x)", "3exp(x)", "xsin(x)", "xcos(x)", "2abs(x)",
    "(x+2)(x+3)", "2(x^2+1)",
])
def test_implicit_multiplication(formula):
    assert parse_text(formula).expressions[0] is not None


@pytest.mark.parametrize("formula", [
    "", "y=", "sin(", "x+", "y=foo(x)", "y=x+y", "x@2", "x^^2", "sqrt(",
    "log(", "(x+1", "x+)", "__import__('os')", "open(x)", "y1=x y2=x^2",
    "x=2", "x<2", "y=x {z<2}", "y=x {x<}", "y=x {x<<2}",
])
def test_invalid_input_has_clear_error(formula):
    with pytest.raises(ValueError):
        parse_text(formula)


@pytest.mark.parametrize("formula", [
    "sqrt(x^2+1)", "cbrt(x)", "abs(x-2)", "floor(x)", "ceil(x)", "round(x)",
    "1/(x-2)", "(x^2+1)/(x-3)", "(2x+1)^3", "sqrt(abs(x))", "log(x^2+1)",
    "exp(-x^2)", "sin(2x)", "sin^2(x)", "e^x",
])
def test_advanced_formulas_have_numeric_samples(formula):
    result = analyze(parse_text(formula).expressions[0], -2, 2, samples=101)
    assert len(result["y"]) == 101


@pytest.mark.parametrize("formula", [
    "1/x", "1/(x-1)", "tan(x)", "sqrt(x)", "ln(x)", "log(x)",
    "1/(x^2-1)", "sqrt(x-1)", "ln(x+2)", "abs(x)", "floor(x)", "ceil(x)",
    "round(x)", "x^2", "sin(x)",
])
def test_edge_cases_return_finite_valid_samples(formula):
    result = analyze(parse_text(formula).expressions[0], -3, 3, samples=301)
    assert result["valid"].any()
    assert np.isfinite(result["y"][result["valid"]]).all()


@pytest.mark.parametrize("source,count", [
    (r"y=2\sin(x)+\cos(x)\{-2\pi\le x\le 2\pi\}", 1),
    ("y1=x^2\ny2=2*x+3\ny3=-x+5", 3),
    ("y=x^2+2 {x<-1}\ny=sin(x) {-1<=x<=2}\ny=ln(x+3) {x>2}", 3),
])
def test_screenshot_regressions(source, count):
    parsed = parse_text(source)
    assert len(parsed.expressions) == count
    for expr in parsed.expressions:
        result = analyze(expr, -10, 10, samples=401)
        assert result["valid"].any()
