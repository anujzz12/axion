"""Input classification and safe mathematical expression parsing."""
from __future__ import annotations

import re
from dataclasses import dataclass

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor, implicit_multiplication_application, parse_expr,
    standard_transformations,
)

X = sp.Symbol("x", real=True)
TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)
ALLOWED = {name: getattr(sp, name) for name in (
    "sin cos tan cot sec csc asin acos atan sinh cosh tanh exp log sqrt Abs "
    "floor ceiling pi E Min Max"
).split()}
ALLOWED.update({"abs": sp.Abs, "ln": sp.log, "log10": lambda value: sp.log(value, 10),
                "log2": lambda value: sp.log(value, 2), "cbrt": lambda value: sp.real_root(value, 3), "x": X, "e": sp.E})
ALLOWED.update({"ceil": sp.ceiling, "round": lambda value: sp.floor(value + sp.Rational(1, 2))})
GLOBALS = {"__builtins__": {}, "Integer": sp.Integer, "Float": sp.Float,
           "Rational": sp.Rational, "Symbol": sp.Symbol, "Function": sp.Function,
           "Add": sp.Add, "Mul": sp.Mul, "Pow": sp.Pow, "Tuple": sp.Tuple,
           "And": sp.And, "Or": sp.Or, "Not": sp.Not, "Eq": sp.Eq,
           "Ne": sp.Ne, "Lt": sp.Lt, "Le": sp.Le, "Gt": sp.Gt, "Ge": sp.Ge,
           "Abs": sp.Abs, "log": sp.log, "sin": sp.sin, "cos": sp.cos,
           "tan": sp.tan, "cot": lambda value: sp.cos(value) / sp.sin(value)}


@dataclass
class ParsedInput:
    kind: str
    expressions: list[sp.Expr]
    labels: list[str]
    points: list[tuple[float, float]]


def _normalize(text: str) -> str:
    text = text.strip()
    for old, new in (("−", "-"), ("–", "-"), ("π", "pi"), ("∞", "oo"),
                     ("≤", "<="), ("≥", ">="), ("≠", "!="), ("×", "*"), ("·", "*")):
        text = text.replace(old, new)
    text = re.sub(r"\\(?:left|right)\b", "", text)
    for command, value in (("pi", "pi"), ("leq", "<="), ("le", "<="),
                           ("geq", ">="), ("ge", ">="), ("neq", "!="),
                           ("cdot", "*"), ("times", "*"), ("sin", "sin"),
                           ("cos", "cos"), ("tan", "tan"), ("cot", "cot"),
                           ("sec", "sec"), ("csc", "csc"), ("ln", "ln"),
                           ("sqrt", "sqrt"), ("abs", "abs"), ("log", "log"),
                           ("exp", "exp")):
        text = text.replace("\\" + command, value)
    text = re.sub(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"((\1)/(\2))", text)
    text = re.sub(r"\\sqrt\s*\{([^{}]+)\}", r"sqrt(\1)", text)
    text = text.replace("\\{", "{").replace("\\}", "}")
    text = text.replace("**", "^")
    text = re.sub(r"\b(sin|cos|tan|cot|sec|csc)\s*\^\s*(\d+)\s*\(\s*([^()]*)\s*\)",
                  r"(\1(\3))^\2", text)
    return text


def _sympy(text: str) -> sp.Expr:
    text = _normalize(text).replace("{", "(").replace("}", ")")
    text = re.sub(r"x(?=(?:sin|cos|tan|cot|sec|csc|ln|log|sqrt|abs|exp)\s*\()", "x*", text)
    text = re.sub(r"\|([^|]+)\|", r"abs(\1)", text)
    if not text:
        raise ValueError("Enter an equation or expression.")
    if not re.fullmatch(r"[A-Za-z0-9_\s+*/^().,!<>=|&-]+", text):
        raise ValueError("Use standard arithmetic and supported functions only.")
    names = set(re.findall(r"[A-Za-z_]\w*", re.sub(r"(?<=\d)[eE][+-]?\d+", "", text)))
    unsupported = names - set(ALLOWED)
    if unsupported:
        raise ValueError("Unsupported name(s): " + ", ".join(sorted(unsupported)) + ". Use x and supported functions such as sin, log, sqrt, and abs.")
    try:
        expr = parse_expr(text, local_dict=ALLOWED.copy(), transformations=TRANSFORMS,
                          evaluate=True, global_dict=GLOBALS)
    except Exception as exc:
        raise ValueError(f"Could not parse expression: {exc}") from exc
    if expr.free_symbols - {X}:
        raise ValueError("Only the variable x is supported in equations.")
    return expr


def _condition(condition: str) -> sp.logic.boolalg.Boolean:
    condition = _normalize(condition)
    parts = re.split(r"\s+or\s+", condition, flags=re.I)
    if len(parts) > 1:
        return sp.Or(*(_condition(part) for part in parts))
    parts = re.split(r"\s+and\s+", condition, flags=re.I)
    if len(parts) > 1:
        return sp.And(*(_condition(part) for part in parts))
    # Convert chained comparisons into conjunctions before parsing.
    chain = re.fullmatch(r"\s*(.+?)\s*(<=|<)\s*x\s*(<=|<)\s*(.+?)\s*", condition)
    if chain:
        lo, lop, hip, hi = chain.groups()
        lower, upper = _sympy(lo), _sympy(hi)
        return sp.And(X <= upper if hip == "<=" else X < upper,
                      X >= lower if lop == "<=" else X > lower)
    single = re.fullmatch(r"\s*x\s*(<=|>=|!=|<|>)\s*(.+?)\s*", condition)
    if single:
        op, rhs = single.groups()
        value = _sympy(rhs)
        return {"<": sp.Lt, "<=": sp.Le, ">": sp.Gt, ">=": sp.Ge, "!=": sp.Ne}[op](X, value)
    # Inequality parsing is safe after validating the restricted token alphabet.
    condition = condition.replace("!=", " != ")
    try:
        result = parse_expr(condition, local_dict=ALLOWED.copy(), transformations=TRANSFORMS,
                            evaluate=True, global_dict=GLOBALS)
    except Exception as exc:
        raise ValueError("Invalid domain restriction. Use conditions such as {x < -1} or {-1 <= x <= 2}.") from exc
    if not isinstance(result, (sp.logic.boolalg.Boolean, sp.core.relational.Relational)):
        raise ValueError("A domain restriction must compare x with a number or expression.")
    if result.free_symbols - {X}:
        raise ValueError("Only x is supported in domain restrictions.")
    return result


def parse_expression(source: str) -> sp.Expr:
    text = _normalize(source)
    # Extract one trailing brace restriction; braces inside the formula are not accepted.
    match = re.search(r"\{([^{}]*)\}\s*$", text)
    restriction = None
    if match and re.search(r"(?:<=|>=|!=|<|>)", match.group(1)):
        restriction = match.group(1)
        text = text[:match.start()].strip()
    # Labels on explicit functions, e.g. y1=, y=, f(x)=.
    equality = re.match(r"^\s*([A-Za-z]\w*(?:\s*\(\s*x\s*\))?)\s*=\s*(.+)$", text)
    if equality:
        left, right = equality.groups()
        if re.fullmatch(r"(?:y\d*|[fgh]\s*\(\s*x\s*\))", left.strip(), re.I):
            text = right
    expr = _sympy(text)
    if isinstance(expr, sp.core.relational.Relational):
        raise ValueError("Enter a function of x, such as y = x^2. Put inequalities inside braces as a domain restriction.")
    if restriction is not None:
        expr = sp.Piecewise((expr, _condition(restriction)), (sp.nan, True))
    return expr


def parse_text(source: str) -> ParsedInput:
    text = source.strip()
    if not text:
        raise ValueError("Enter an equation or coordinate points.")
    pairs = re.findall(r"\(\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*,\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*\)", text)
    residue = re.sub(r"\(\s*-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\s*,\s*-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\s*\)", "", text)
    if pairs and not residue.strip(" ,\n\t"):
        points = [(float(a), float(b)) for a, b in pairs]
        if len(points) < 2:
            raise ValueError("At least two coordinate points are required.")
        return ParsedInput("points", [], [], points)
    lines = [line.strip() for line in re.split(r"[\n;]+", text) if line.strip()]
    if len(lines) == 1:
        # Commas are separators only when the right side clearly starts another equation.
        lines = [part.strip() for part in re.split(r",\s*(?=(?:y\d*|[fgh]\s*\(\s*x\s*\))\s*=)", lines[0]) if part.strip()]
    if len(lines) > 20:
        raise ValueError("Plot at most 20 equations at a time.")
    expressions, labels = [], []
    for line in lines:
        expressions.append(parse_expression(line))
        labels.append(line)
    return ParsedInput("equations", expressions, labels, [])
