"""Symbolic and numerical analysis for explicit single-variable functions."""
from __future__ import annotations

import numpy as np
import sympy as sp
from scipy.optimize import brentq, minimize_scalar

from .parser import X


def _finite_eval(expr, values):
    try:
        fn = sp.lambdify(X, expr, modules=["numpy"])
        with np.errstate(all="ignore"):
            result = np.asarray(fn(values), dtype=float)
        return np.broadcast_to(result, np.shape(values)).astype(float)
    except (TypeError, ValueError, NameError, NotImplementedError):
        # Some valid SymPy derivatives (floor, ceiling, real cube roots) do not
        # have NumPy lambdify implementations. Fall back to pointwise numeric
        # evaluation and mark unsupported points as undefined.
        scalar = sp.lambdify(X, expr, modules=["math", {"ceiling": np.ceil, "floor": np.floor}])
        output = np.full(np.shape(values), np.nan, dtype=float)
        for index, value in np.ndenumerate(np.asarray(values)):
            try:
                output[index] = float(scalar(float(value)))
            except (ArithmeticError, TypeError, ValueError, OverflowError, NameError):
                continue
        return output


def analyze(expr: sp.Expr, xmin: float, xmax: float, samples: int = 1600) -> dict:
    xs = np.linspace(xmin, xmax, samples)
    ys = _finite_eval(expr, xs)
    valid = np.isfinite(ys)
    deriv = sp.diff(expr, X)
    try:
        dydx = _finite_eval(deriv, xs)
    except Exception:
        dydx = np.gradient(ys, xs)
    roots = []
    try:
        for root in sp.solve(expr, X):
            if root.is_real and root.is_number and xmin <= float(root) <= xmax:
                roots.append(float(root))
    except Exception:
        pass
    for i in range(samples - 1):
        if valid[i] and valid[i + 1] and ys[i] * ys[i + 1] < 0:
            try:
                roots.append(float(brentq(lambda t: float(_finite_eval(expr, np.array([t]))[0]), xs[i], xs[i + 1])))
            except (ValueError, TypeError, OverflowError):
                continue
    roots = sorted({round(r, 9) for r in roots})
    extrema = []
    finite_idx = np.flatnonzero(valid)
    if len(finite_idx):
        imin, imax = finite_idx[np.argmin(ys[finite_idx])], finite_idx[np.argmax(ys[finite_idx])]
        extrema = [{"kind": "sampled minimum", "x": float(xs[imin]), "y": float(ys[imin])},
                   {"kind": "sampled maximum", "x": float(xs[imax]), "y": float(ys[imax])}]
    critical = []
    dvalid = np.isfinite(dydx)
    for i in range(samples - 1) if not deriv.has(sp.Derivative) else ():
        if dvalid[i] and dvalid[i + 1] and dydx[i] * dydx[i + 1] < 0:
            try:
                cx = brentq(lambda t: float(_finite_eval(deriv, np.array([t]))[0]), xs[i], xs[i + 1])
                critical.append({"x": float(cx), "y": float(_finite_eval(expr, np.array([cx]))[0])})
            except (ValueError, TypeError):
                pass
    area = float(np.trapezoid(np.where(valid, ys, np.nan), xs)) if valid.all() else None
    return {"x": xs, "y": ys, "valid": valid, "derivative": sp.sstr(deriv),
            "roots": roots, "y_intercept": float(_finite_eval(expr, np.array([0.0]))[0]) if np.isfinite(_finite_eval(expr, np.array([0.0]))[0]) else None,
            "extrema": extrema, "critical_points": critical, "area": area,
            "window": (xmin, xmax), "valid_fraction": float(valid.mean())}
