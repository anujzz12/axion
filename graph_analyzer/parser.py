"""Input classification and safe mathematical expression parsing."""
from __future__ import annotations

import re
from dataclasses import dataclass

import sympy as sp
from sympy.parsing.sympy_parser import (convert_xor, implicit_multiplication_application,
    parse_expr, standard_transformations)

X = sp.Symbol("x", real=True)
TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)
ALLOWED = {name: getattr(sp, name) for name in (
    "sin cos tan asin acos atan sinh cosh tanh exp log sqrt Abs pi E".split()
)}
ALLOWED.update({"abs": sp.Abs, "log": sp.log, "ln": sp.log, "x": X})


@dataclass
class ParsedInput:
    kind: str
    expressions: list[sp.Expr]
    labels: list[str]
    points: list[tuple[float, float]]


def parse_expression(source: str) -> sp.Expr:
    text = source.strip().replace("−", "-").replace("²", "^2").replace("³", "^3")
    # Normalize common LaTeX commands used when copying equations.
    text = (text.replace(r"\left", "").replace(r"\right", "")
            .replace(r"\ln", "log").replace(r"\sin", "sin")
            .replace(r"\cos", "cos").replace(r"\tan", "tan")
            .replace(r"\cdot", "*").replace(r"\times", "*")
            .replace(r"\leq", "<=").replace(r"\le", "<=")
            .replace(r"\geq", ">=").replace(r"\ge", ">="))
    text = re.sub(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"((\1)/(\2))", text)
    # Accept domain suffixes both in braces and in the common |x| <= 2pi form.
    chain_domain = re.search(r"\|?\s*(-?\d+(?:\.\d+)?\s*\*?\s*pi|-?\d+(?:\.\d+)?)\s*\|?\s*(<=|<)\s*x\s*(<=|<)\s*\|?\s*(\d+(?:\.\d+)?\s*\*?\s*pi|\d+(?:\.\d+)?)\s*\|?\s*$", text)
    if chain_domain:
        lo, lop, hip, hi = chain_domain.groups()
        body = text[:chain_domain.start()].rstrip()
        def bound_value(value):
            value = re.sub(r"\s*\*?\s*pi", "*pi", value)
            return parse_expr(value, local_dict=ALLOWED.copy(), transformations=TRANSFORMS,
                global_dict={"__builtins__": {}, "Integer": sp.Integer, "Float": sp.Float, "Rational": sp.Rational,
                             "Symbol": sp.Symbol, "Function": sp.Function, "Add": sp.Add, "Mul": sp.Mul, "Pow": sp.Pow})
        lower, upper = bound_value(lo), bound_value(hi)
        test = sp.And(X >= lower if lop == "<=" else X > lower,
                      X <= upper if hip == "<=" else X < upper)
        return sp.Piecewise((parse_expression(body), test), (sp.nan, True))
    unbraced = re.search(r"\|\s*x\s*\|\s*(?:<=|<)\s*(?:\d+(?:\.\d+)?\s*\*?\s*pi|\d+(?:\.\d+)?)\s*$", text)
    if unbraced:
        condition = unbraced.group(0).strip()
        body = text[:unbraced.start()].rstrip()
        m = re.fullmatch(r"\|\s*x\s*\|\s*(<=|<)\s*(\d+(?:\.\d+)?\s*\*?\s*pi|\d+(?:\.\d+)?)", condition)
        op, bound = m.groups()
        bound_expr = parse_expr(bound.replace("pi", "*pi"), local_dict=ALLOWED.copy(), transformations=TRANSFORMS,
            global_dict={"__builtins__": {}, "Integer": sp.Integer, "Float": sp.Float, "Rational": sp.Rational,
                         "Symbol": sp.Symbol, "Function": sp.Function, "Add": sp.Add, "Mul": sp.Mul, "Pow": sp.Pow})
        test = sp.Le(sp.Abs(X), bound_expr) if op == "<=" else sp.Lt(sp.Abs(X), bound_expr)
        return sp.Piecewise((parse_expression(body), test), (sp.nan, True))
    domain = re.search(r"\{\s*(.*?)\s*\}\s*$", text)
    if domain and re.search(r"\bx\b", domain.group(1)) and re.search(r"<=|>=|<|>", domain.group(1)):
        condition = domain.group(1).replace(r"\le", "<=").replace(r"\ge", ">=")
        body = text[:domain.start()].strip()
        chain = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*(<=|<)\s*x\s*(<=|<)\s*(-?\d+(?:\.\d+)?)", condition)
        if chain:
            lo, lop, hip, hi = chain.groups()
            test = sp.And(X >= float(lo) if lop == "<=" else X > float(lo),
                          X <= float(hi) if hip == "<=" else X < float(hi))
        else:
            test = None
            for op, rel in (("<=", sp.Le), (">=", sp.Ge), ("<", sp.Lt), (">", sp.Gt)):
                match = re.fullmatch(rf"x\s*{re.escape(op)}\s*(-?\d+(?:\.\d+)?)", condition)
                if match:
                    test = rel(X, float(match.group(1)))
                    break
            if test is None:
                raise ValueError("Use restrictions like {x < -1}, {-1 <= x <= 2}, or {x > 2}.")
        return sp.Piecewise((parse_expression(body), test), (sp.nan, True))
    text = text.replace("{", "(").replace("}", ")")
    # Paired vertical bars denote absolute value: |expression| -> abs(expression).
    text = re.sub(r"\|([^|]+)\|", r"abs(\1)", text)
    if not text:
        raise ValueError("Enter an equation or expression.")
    if "=" in text:
        left, right = text.split("=", 1)
        left = left.strip().removeprefix("y").strip() or "0"
        right = right.strip().removeprefix("y").strip() or "0"
        text = f"({right})-({left})"
    if not re.fullmatch(r"[\w\s+*/^().,!-]+", text):
        raise ValueError("Use standard arithmetic and supported functions only.")
    identifiers = set(re.findall(r"[A-Za-z_]\w*", text))
    unsupported = identifiers - set(ALLOWED)
    if unsupported:
        raise ValueError("Unsupported name(s): " + ", ".join(sorted(unsupported)) +
                         ". Use x and standard functions such as sin, cos, exp, log, sqrt, and abs.")
    try:
        expr = parse_expr(text, local_dict=ALLOWED.copy(), transformations=TRANSFORMS,
                          evaluate=True, global_dict={"__builtins__": {}, "Integer": sp.Integer,
                          "Float": sp.Float, "Rational": sp.Rational, "Symbol": sp.Symbol,
                          "Function": sp.Function, "Add": sp.Add, "Mul": sp.Mul, "Pow": sp.Pow})
    except Exception as exc:
        raise ValueError(f"Could not parse expression: {exc}") from exc
    if expr.free_symbols - {X}:
        raise ValueError("Only the variable x is supported in equations.")
    if expr.has(sp.Derivative, sp.Integral, sp.Lambda):
        raise ValueError("Derivative, Integral, and Lambda expressions are not accepted as input.")
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
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    expressions, labels = [], []
    for line in lines:
        expr = parse_expression(line)
        expressions.append(expr)
        labels.append(line)
    return ParsedInput("equations", expressions, labels, [])
