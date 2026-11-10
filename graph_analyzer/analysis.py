"""Descriptive statistics and least-squares analysis for measured data."""
import numpy as np
from scipy.stats import linregress


def analyze_data(x, y):
    if len(x) != len(y) or len(x) < 1:
        raise ValueError("At least one paired observation is required.")
    if len(x) < 2 or np.ptp(x) == 0:
        return {"count": len(x), "slope": None, "intercept": None, "correlation": None,
                "r2": None, "mean_abs_residual_pct": None, "predicted": None}
    fit = linregress(x, y)
    predicted = fit.intercept + fit.slope * x
    ss_res = float(np.sum((y - predicted) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot else None
    mean_abs = float(np.mean(np.abs(y)))
    error_pct = float(np.mean(np.abs(y - predicted)) / mean_abs * 100) if mean_abs else None
    return {"count": len(x), "slope": float(fit.slope), "intercept": float(fit.intercept),
            "correlation": float(fit.rvalue) if np.isfinite(fit.rvalue) else None,
            "r2": r2, "mean_abs_residual_pct": error_pct, "predicted": predicted}
