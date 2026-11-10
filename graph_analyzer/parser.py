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
ALLOWED.update({"abs": sp.Abs, "x": X})


@dataclass
class ParsedInput:
    kind: str
    expressions: list[sp.Expr]
    labels: list[str]
    points: list[tuple[float, float]]


def parse_expression(source: str) -> sp.Expr:
    text = source.strip().replace("−", "-")
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
