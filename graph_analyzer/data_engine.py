"""Load and validate uploaded or pasted tabular observations."""
from __future__ import annotations

from io import StringIO, BytesIO
import json
import re
from itertools import combinations

import numpy as np
import pandas as pd


def load_upload(upload) -> pd.DataFrame:
    filename = getattr(upload, "filename", None) or getattr(upload, "name", "")
    name = str(filename).lower()
    if hasattr(upload, "read"):
        raw = upload.read()
        if hasattr(upload, "seek"):
            upload.seek(0)
    elif hasattr(upload, "getvalue"):
        raw = upload.getvalue()
    else:
        raise ValueError("Unsupported upload stream.")
    if name.endswith(".csv"):
        frame = pd.read_csv(BytesIO(raw))
    elif name.endswith(".tsv"):
        frame = pd.read_csv(BytesIO(raw), sep="\t")
    elif name.endswith(".txt"):
        frame = pd.read_csv(BytesIO(raw), sep=None, engine="python")
    elif name.endswith((".xlsx", ".xls")):
        frame = pd.read_excel(BytesIO(raw))
    elif name.endswith(".json"):
        data = json.loads(raw.decode("utf-8"))
        if isinstance(data, list):
            frame = pd.json_normalize(data)
        elif isinstance(data, dict) and data and all(isinstance(value, list) for value in data.values()):
            frame = pd.DataFrame(data)
        else:
            frame = pd.json_normalize(data)
    else:
        raise ValueError("Supported upload formats: CSV, TSV, TXT, XLS, XLSX, and JSON.")
    if frame.empty:
        raise ValueError("The uploaded dataset has no rows.")
    return frame


def load_pasted_table(text: str) -> pd.DataFrame:
    if not text.strip():
        raise ValueError("Paste a table with column headers and numeric values.")
    pairs = re.findall(r"\(\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*,\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*\)", text)
    remainder = re.sub(r"\(\s*-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\s*,\s*-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\s*\)", "", text)
    if pairs and not remainder.strip(" ,\n\t"):
        return pd.DataFrame([(float(x), float(y)) for x, y in pairs], columns=["X", "Y"])
    nonempty_lines = [line for line in text.splitlines() if line.strip()]
    first_line = nonempty_lines[0]
    delimiter = next((candidate for candidate in (",", "\t", ";") if candidate in first_line), None)
    if delimiter is None:
        split_lines = [re.split(r"\s+", line.strip()) for line in nonempty_lines]
        if split_lines and len(split_lines[0]) > 1 and all(len(row) == len(split_lines[0]) for row in split_lines):
            delimiter = r"\s+"
    try:
        if delimiter is None:
            raw = pd.DataFrame({0: nonempty_lines})
        else:
            raw = pd.read_csv(StringIO(text), sep=delimiter, engine="python", header=None)
    except Exception as exc:
        raise ValueError(f"Could not read the pasted table: {exc}") from exc
    if raw.shape[1] < 1:
        raise ValueError("No values were found. Paste one column or a table of values.")
    first_row_is_numeric = pd.to_numeric(raw.iloc[0], errors="coerce").notna().all()
    if first_row_is_numeric:
        frame = raw
        frame.columns = [f"Column {i + 1}" for i in range(frame.shape[1])]
    elif raw.shape[1] == 1:
        following_values = pd.to_numeric(raw.iloc[1:, 0], errors="coerce").notna().sum()
        if following_values:
            frame = raw.iloc[1:].copy()
            frame.columns = [str(raw.iloc[0, 0]).strip() or "Column 1"]
        else:
            frame = raw.copy()
            frame.columns = ["Column 1"]
    else:
        frame = raw.iloc[1:].copy()
        frame.columns = [str(value).strip() for value in raw.iloc[0]]
        if not all(frame.columns):
            frame.columns = [f"Column {i + 1}" for i in range(frame.shape[1])]
    if frame.empty:
        raise ValueError("Add at least one row of X and Y values below the column headers.")
    return frame


def numeric_xy(frame: pd.DataFrame, xcol: str, ycol: str):
    cleaned = frame[[xcol, ycol]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(cleaned) < 1:
        raise ValueError("Select numeric X and Y columns with at least one valid row.")
    return cleaned[xcol].to_numpy(dtype=float), cleaned[ycol].to_numpy(dtype=float)


def inspect_dataset(frame: pd.DataFrame) -> dict:
    """Classify columns and build a factual, compact summary of a dataset."""
    if frame.empty or len(frame.columns) == 0:
        raise ValueError("The dataset has no rows or columns to plot.")

    numeric, dates, categorical = [], [], []
    converted = {}
    missing = frame.isna().sum().to_dict()
    min_valid = max(1, int(np.ceil(len(frame) * 0.6)))
    for col in frame.columns:
        series = frame[col]
        if pd.api.types.is_bool_dtype(series):
            categorical.append(col)
            converted[col] = series
            continue
        nums = pd.to_numeric(series, errors="coerce")
        if nums.notna().sum() >= min_valid:
            numeric.append(col)
            converted[col] = nums
            missing[col] = len(frame) - int(nums.notna().sum())
            continue
        if pd.api.types.is_datetime64_any_dtype(series):
            parsed = pd.to_datetime(series, errors="coerce")
            dates.append(col)
            converted[col] = parsed
            missing[col] = len(frame) - int(parsed.notna().sum())
            continue
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
            parsed = pd.to_datetime(series, errors="coerce", format="mixed")
            if parsed.notna().sum() >= min_valid and parsed.nunique() > 1:
                dates.append(col)
                converted[col] = parsed
                missing[col] = len(frame) - int(parsed.notna().sum())
                continue
        categorical.append(col)
        converted[col] = series

    numeric_rows = []
    for col in numeric:
        values = converted[col].dropna()
        numeric_rows.append({
            "Column": str(col), "Valid values": int(values.size), "Missing": int(missing[col]),
            "Mean": float(values.mean()), "Median": float(values.median()),
            "Std. dev.": float(values.std()) if values.size > 1 else None,
            "Minimum": float(values.min()), "Maximum": float(values.max()),
        })
    category_rows = []
    for col in categorical:
        values = frame[col].dropna()
        top = values.astype(str).value_counts().head(3)
        category_rows.append({
            "Column": str(col), "Unique values": int(values.nunique()), "Missing": int(missing[col]),
            "Most common values": ", ".join(f"{v} ({n})" for v, n in top.items()) or "—",
        })
    date_rows = []
    for col in dates:
        values = converted[col].dropna()
        date_rows.append({"Column": str(col), "Start": str(values.min()), "End": str(values.max()),
                          "Valid dates": int(values.size), "Missing": int(missing[col])})

    lines = [f"This table has {len(frame):,} rows and {len(frame.columns):,} columns."]
    lines.append(f"I found {len(numeric)} numeric, {len(dates)} date/time, and {len(categorical)} categorical columns.")
    missing_cols = [(str(col), int(count)) for col, count in missing.items() if count]
    if missing_cols:
        names = ", ".join(f"{col} ({count:,})" for col, count in missing_cols[:5])
        lines.append(f"Missing values appear in {names}{' and other columns' if len(missing_cols) > 5 else ''}.")
    else:
        lines.append("There are no missing cells.")
    corr_candidates = []
    corr_columns = numeric[:50]
    if len(corr_columns) >= 2:
        corr_frame = pd.DataFrame({col: converted[col] for col in corr_columns})
        corr_matrix = corr_frame.corr()
        for left, right in combinations(corr_columns, 2):
            corr = corr_matrix.loc[left, right]
            paired_count = int(corr_frame[[left, right]].dropna().shape[0])
            if paired_count >= 3 and pd.notna(corr):
                corr_candidates.append((abs(float(corr)), left, right, float(corr), paired_count))
    if corr_candidates:
        _, left, right, corr, count = max(corr_candidates)
        lines.append(f"The strongest pairwise linear association is between {left} and {right} (r = {corr:.2f}, {count:,} paired rows). This describes association, not cause.")
    return {"rows": len(frame), "columns": len(frame.columns), "numeric": numeric,
            "dates": dates, "categorical": categorical, "converted": converted,
            "numeric_summary": pd.DataFrame(numeric_rows),
            "category_summary": pd.DataFrame(category_rows),
            "date_summary": pd.DataFrame(date_rows), "prose": " ".join(lines)}


def recommend_chart(info: dict) -> str | None:
    """Choose a useful starting chart from the dataset's column types."""
    if info["dates"] and info["numeric"]:
        return "Line"
    if len(info["numeric"]) >= 2:
        return "Scatter"
    if info["categorical"] and info["numeric"]:
        return "Bar"
    if info["numeric"]:
        return "Histogram"
    if info["categorical"]:
        return "Bar"
    return None
