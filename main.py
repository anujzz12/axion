import json
import os
import re
import time
import urllib.request
from pathlib import Path

from flask import Flask, jsonify, render_template, request
import numpy as np
import pandas as pd

from graph_analyzer.parser import parse_text
from graph_analyzer.math_engine import analyze
from graph_analyzer.data_engine import (
    load_pasted_table,
    load_upload,
    inspect_dataset,
    recommend_chart,
)
from graph_analyzer.plotting import function_figure, dataset_figure
from graph_analyzer.exporting import csv_bytes

app = Flask(
    __name__,
    template_folder="website/templates",
    static_folder="website/static",
    static_url_path="/website/static",
)

REPO = "shuvamm939-glitch/AXION"
PYCALC_URL = os.environ.get("PYCALC_URL", "https://pycalculator.vercel.app")
BASE_DIR = Path(__file__).parent

LANG_COLORS = {
    "Python": "#3572A5",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "JavaScript": "#f1e05a",
    "Jinja": "#a52a22",
    "Shell": "#89e051",
}
_lang_cache = {"expires": 0, "data": None}


def repo_languages():
    if time.time() < _lang_cache["expires"]:
        return _lang_cache["data"]

    headers = {"User-Agent": "axion-site", "Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]

    data = None
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{REPO}/languages", headers=headers
        )
        with urllib.request.urlopen(req, timeout=2) as response:
            raw = json.load(response)
        total = sum(raw.values())
        if total:
            data = [
                {
                    "name": name,
                    "pct": size / total * 100,
                    "label": f"{round(size / total * 100)}%"
                    if size / total >= 0.01
                    else "<1%",
                    "color": LANG_COLORS.get(name, "#8b9096"),
                }
                for name, size in sorted(raw.items(), key=lambda item: -item[1])
            ]
    except Exception:
        data = None

    _lang_cache["data"] = data
    _lang_cache["expires"] = time.time() + (3600 if data else 300)
    return data


def read_requirements():
    try:
        lines = (BASE_DIR / "requirements.txt").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    packages = []
    for line in lines:
        line = line.split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        name = re.split(r"[<>=!~\[;\s]", line, maxsplit=1)[0]
        pinned = re.search(r"==\s*([\w.]+)", line)
        packages.append({"name": name, "version": pinned.group(1) if pinned else ""})
    return packages


@app.context_processor
def footer_data():
    return {
        "repo": REPO,
        "languages": repo_languages(),
        "deps": read_requirements(),
        "pycalc_url": PYCALC_URL,
    }


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/functions")
def functions():
    return render_template("functions.html")


@app.route("/data")
def data():
    return render_template("data.html")


@app.route("/api/plot/function", methods=["POST"])
def api_plot_function():
    payload = request.get_json(silent=True) or {}
    expression_text = payload.get("expression", "").strip()
    try:
        xmin = float(payload.get("xmin", -10))
        xmax = float(payload.get("xmax", 10))
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "Invalid X range limits."}), 400

    if not expression_text:
        return jsonify({"ok": False, "error": "Please enter an equation."}), 400
    if xmin >= xmax:
        return jsonify({"ok": False, "error": "X minimum must be less than X maximum."}), 400

    try:
        parsed = parse_text(expression_text)
        if parsed.kind != "equations":
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "For coordinate values, use the Scientific Data page.",
                    }
                ),
                400,
            )

        series = []
        serializable_series = []
        export_rows = []

        for expr, label in zip(parsed.expressions, parsed.labels):
            analysis_res = analyze(expr, xmin, xmax)
            series.append((label, analysis_res))

            # prepare CSV export rows
            for xx, yy, valid in zip(
                analysis_res["x"], analysis_res["y"], analysis_res["valid"]
            ):
                export_rows.append(
                    {
                        "function": label,
                        "x": round(float(xx), 6),
                        "y": round(float(yy), 6) if valid else None,
                    }
                )

            # building serializable analysis dict
            serializable_series.append(
                {
                    "label": label,
                    "derivative": analysis_res.get("derivative", ""),
                    "roots": [float(r) for r in analysis_res.get("roots", [])],
                    "y_intercept": (
                        float(analysis_res["y_intercept"])
                        if analysis_res.get("y_intercept") is not None
                        else None
                    ),
                    "extrema": analysis_res.get("extrema", []),
                    "critical_points": analysis_res.get("critical_points", []),
                    "area": (
                        float(analysis_res["area"])
                        if analysis_res.get("area") is not None
                        else None
                    ),
                    "valid_fraction": float(analysis_res.get("valid_fraction", 0)),
                }
            )

        fig = function_figure(series, xmin, xmax, title="Function Plot")
        fig_json = json.loads(fig.to_json())

        csv_df = pd.DataFrame(export_rows)
        csv_str = csv_df.to_csv(index=False)

        return jsonify(
            {
                "ok": True,
                "figure": fig_json,
                "series": serializable_series,
                "csv": csv_str,
            }
        )

    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/api/analyze/data", methods=["POST"])
def api_analyze_data():
    source = request.form.get("source", "paste")

    try:
        if source == "upload":
            file = request.files.get("file")
            if not file or not file.filename:
                return jsonify({"ok": False, "error": "Please select a file to upload."}), 400
            frame = load_upload(file)
        else:
            pasted_text = request.form.get("pasted_text", "").strip()
            if not pasted_text:
                return jsonify({"ok": False, "error": "Please paste data table values."}), 400
            frame = load_pasted_table(pasted_text)

        info = inspect_dataset(frame)
        rec = recommend_chart(info)



        def clean_records(df):
            if df is None or df.empty:
                return []
            return json.loads(df.replace({np.nan: None}).to_json(orient="records"))

        num_summary = clean_records(info.get("numeric_summary"))
        cat_summary = clean_records(info.get("category_summary"))
        date_summary = clean_records(info.get("date_summary"))


        preview_df = frame.head(30).replace({np.nan: None})
        preview_rows = json.loads(preview_df.to_json(orient="records"))
        raw_records = json.loads(frame.replace({np.nan: None}).to_json(orient="records"))

        serializable_info = {
            "rows": int(info["rows"]),
            "columns": int(info["columns"]),
            "numeric": [str(c) for c in info["numeric"]],
            "dates": [str(c) for c in info["dates"]],
            "categorical": [str(c) for c in info["categorical"]],
            "prose": info.get("prose", ""),
            "recommended": rec,
        }

        csv_str = frame.to_csv(index=False)

        return jsonify(
            {
                "ok": True,
                "info": serializable_info,
                "numeric_summary": num_summary,
                "category_summary": cat_summary,
                "date_summary": date_summary,
                "columns": [str(c) for c in frame.columns],
                "preview_rows": preview_rows,
                "raw_records": raw_records,
                "csv": csv_str,
            }
        )

    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/api/render/data-chart", methods=["POST"])
def api_render_data_chart():
    payload = request.get_json(silent=True) or {}
    raw_records = payload.get("data_json", [])
    chart = payload.get("chart", "Scatter")
    xcol = payload.get("xcol")
    ycol = payload.get("ycol")
    colorcol = payload.get("colorcol") or None
    thirdcol = payload.get("thirdcol") or None

    if not raw_records:
        return jsonify({"ok": False, "error": "No data found to plot."}), 400




    if xcol in ("", "All values", "None"):
        xcol = None
    if ycol in ("", "Count / frequency", "None"):
        ycol = None

    try:
        frame = pd.DataFrame(raw_records)
        info = inspect_dataset(frame)
        fig = dataset_figure(frame, info, chart, xcol, ycol, colorcol, thirdcol)
        return jsonify({"ok": True, "figure": json.loads(fig.to_json())})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


if __name__ == "__main__":
    app.run(debug=True, port=5000)
