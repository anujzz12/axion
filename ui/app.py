"""Streamlit interface for plotting functions and exploring tabular data."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from graph_analyzer.data_engine import inspect_dataset, load_pasted_table, load_upload, recommend_chart
from graph_analyzer.exporting import csv_bytes, html_bytes
from graph_analyzer.math_engine import analyze
from graph_analyzer.parser import parse_text
from graph_analyzer.plotting import dataset_figure, function_figure


st.set_page_config(page_title="Graph Analyzer", page_icon=":material/show_chart:", layout="wide")
st.title("Graph Analyzer")
st.caption("Plot a function or explore a dataset.")

with st.sidebar:
    st.subheader("Plot range")
    xmin = st.number_input("X minimum", value=-10.0, step=1.0)
    xmax = st.number_input("X maximum", value=10.0, step=1.0)
    st.caption("These limits apply to function plots.")

plot_kind = st.segmented_control(
    "What would you like to plot?", ["Function", "Data"], default="Function", key="plot_kind"
)
input_col, graph_col = st.columns([1, 1.8], gap="large")

if "history" not in st.session_state:
    st.session_state.history = []

with input_col:
    with st.container(border=True):
        st.subheader("Input")
        if plot_kind == "Function":
            with st.form("function_form"):
                expression_text = st.text_area(
                    "Equation(s)", value="y = x^2 - 4", height=105,
                    help="Use x as the variable. Put each function on its own line.",
                )
                st.caption("Example: `y = sin(x)` or `y = x^2 - 4`")
                submitted = st.form_submit_button("Plot function", type="primary", width="stretch")
            if submitted:
                st.session_state.pop("result", None)
                if xmin >= xmax:
                    st.error("The minimum must be less than the maximum.")
                else:
                    try:
                        parsed = parse_text(expression_text)
                        if parsed.kind != "equations":
                            raise ValueError("For coordinate values, choose Data and enter one X,Y pair per row.")
                        series = [(label, analyze(expr, xmin, xmax)) for expr, label in zip(parsed.expressions, parsed.labels)]
                        st.session_state.result = {"kind": "equations", "series": series}
                        st.session_state.history.insert(0, expression_text.strip())
                        st.session_state.history = st.session_state.history[:8]
                    except Exception as exc:
                        st.error(str(exc), title="Couldn't plot that function")
        else:
            source = st.segmented_control(
                "Data source", ["Paste values", "Upload file"], default="Paste values", key="data_source"
            )
            with st.form("data_form"):
                if source == "Paste values":
                    pasted = st.text_area(
                        "Paste your data",
                        height=145,
                        placeholder="date,temperature,location\n2026-01-01,18,North\n2026-01-02,21,South",
                        help="A header row is optional. Coordinate pairs like (1, 2), (2, 4) are supported too.",
                    )
                    st.caption("CSV-style rows work best. You can include dates, labels, and several measurements.")
                    upload = None
                else:
                    upload = st.file_uploader(
                        "Choose a CSV, TSV, text, Excel, or JSON file",
                        type=["csv", "tsv", "txt", "xlsx", "xls", "json"],
                    )
                    pasted = ""
                submitted = st.form_submit_button("Explore data", type="primary", width="stretch")
            if submitted:
                st.session_state.pop("result", None)
                try:
                    if source == "Upload file" and upload is None:
                        raise ValueError("Choose a CSV, TSV, text, Excel, or JSON file first.")
                    frame = load_upload(upload) if upload is not None else load_pasted_table(pasted)
                    info = inspect_dataset(frame)
                    if not info["numeric"] and not info["categorical"] and not info["dates"]:
                        raise ValueError("I couldn't find any columns to plot in this data.")
                    st.session_state.result = {"kind": "data", "frame": frame}
                except Exception as exc:
                    st.error(str(exc), title="Couldn't read that data")

result = st.session_state.get("result")
dataset_view = None
with graph_col:
    with st.container(border=True):
        st.subheader("Graph")
        expected_kind = "equations" if plot_kind == "Function" else "data"
        if not result or result["kind"] != expected_kind:
            st.info("Your graph will appear here after you plot.")
            fig = None
        elif result["kind"] == "equations":
            fig = function_figure(result["series"], xmin, xmax)
            st.plotly_chart(
                fig, width="stretch", theme="streamlit",
                alt="Entered functions plotted over the selected X range",
                config={"scrollZoom": True, "displaylogo": False,
                        "toImageButtonOptions": {"format": "png", "filename": "graph", "scale": 2}},
            )
        else:
            frame = result["frame"]
            info = inspect_dataset(frame)
            chart_options: list[str] = []
            if info["dates"]:
                chart_options.append("Line")
            if info["categorical"]:
                chart_options.extend(["Bar", "Pie"])
            if len(info["numeric"]) >= 2:
                chart_options.extend(["Scatter", "Correlation"])
            if len(info["numeric"]) >= 3:
                chart_options.append("3D scatter")
            if info["numeric"]:
                chart_options.extend(["Histogram", "Box"])
            chart_options = list(dict.fromkeys(chart_options))
            suggested = recommend_chart(info)
            default_chart: str = suggested if suggested in chart_options else chart_options[0]
            signature = str(abs(hash((tuple(map(str, frame.columns)), tuple(map(str, info["numeric"])),
                                      tuple(map(str, info["dates"])), tuple(map(str, info["categorical"]))))))
            selected_chart = st.selectbox("Chart", chart_options, index=chart_options.index(default_chart), key=f"dataset_chart_{signature}")
            chart: str = str(selected_chart if selected_chart is not None else default_chart)

            xname = yname = colorname = zname = None
            if chart in ("Line", "Scatter", "Bar", "Box", "Pie", "3D scatter"):
                if chart == "Line":
                    x_options, y_options = info["dates"] + info["numeric"] + info["categorical"], info["numeric"]
                    if not y_options:
                        y_options = ["Row count"]
                elif chart in ("Scatter", "3D scatter"):
                    x_options = info["numeric"]
                    y_options = [col for col in info["numeric"] if col != xname] or info["numeric"]
                elif chart in ("Bar", "Pie"):
                    x_options = info["categorical"]
                    y_options = info["numeric"] + ["Count / frequency"]
                else:
                    x_options = ["All values"] + info["categorical"]
                    y_options = info["numeric"]

                selector_key = f"{signature}_{chart.lower().replace(' ', '_')}"

                if chart == "3D scatter":
                    xcol, ycol, zcol = st.columns(3)
                    with xcol:
                        xname = st.selectbox("X axis", x_options, key=f"data_x_{selector_key}")
                    with ycol:
                        y_options = [col for col in info["numeric"] if col != xname]
                        yname = st.selectbox("Y axis", y_options, key=f"data_y_{selector_key}")
                    with zcol:
                        z_options = [col for col in info["numeric"] if col not in (xname, yname)]
                        zname = st.selectbox("Z axis", z_options, key=f"data_z_{selector_key}")
                else:
                    xcol, ycol = st.columns(2)
                    with xcol:
                        xname = st.selectbox("X axis / category", x_options, key=f"data_x_{selector_key}")
                    with ycol:
                        if chart == "Scatter":
                            y_options = [col for col in info["numeric"] if col != xname] or info["numeric"]
                        yname = st.selectbox("Y axis / value", y_options, key=f"data_y_{selector_key}")
                if chart in ("Line", "Scatter", "3D scatter") and info["categorical"]:
                    colorname = st.selectbox("Group by (optional)", ["No grouping"] + info["categorical"], key=f"data_color_{selector_key}")
                    if colorname == "No grouping":
                        colorname = None

            try:
                if chart == "Histogram":
                    xname = st.selectbox("Values", info["numeric"], key=f"data_hist_{signature}")
                elif chart == "Correlation":
                    st.caption("Each cell shows the correlation between two numeric columns.")
                if chart == "Box" and xname == "All values":
                    xname = None
                if chart in ("Bar", "Pie") and yname == "Count / frequency":
                    yname = None
                fig = dataset_figure(frame, info, chart, xname, yname, colorname, zname)
                st.plotly_chart(
                    fig, width="stretch", theme="streamlit",
                    alt=f"{chart} chart of the supplied dataset",
                    config={"scrollZoom": True, "displaylogo": False,
                            "toImageButtonOptions": {"format": "png", "filename": "graph", "scale": 2}},
                )
                dataset_view = {"frame": frame, "info": info, "fig": fig, "chart": chart}
            except Exception as exc:
                fig = None
                st.error(str(exc), title="Couldn't plot this chart")

if result and result["kind"] == "equations" and plot_kind == "Function":
    with st.container(border=True):
        st.subheader("Results")
        tabs = st.tabs([label for label, _ in result["series"]])
        for (label, analysis), tab in zip(result["series"], tabs):
            with tab:
                st.code(f"f(x) = {label}", language=None)
                st.write(f"**Derivative:** `{analysis['derivative']}`")
                st.write("**Roots in this range:**", ", ".join(f"{r:.6g}" for r in analysis["roots"]) or "None found")
                st.write("**Y-intercept:**", f"(0, {analysis['y_intercept']:.6g})" if analysis["y_intercept"] is not None else "Undefined")
                st.caption(f"Range checked: x = {xmin:g} to {xmax:g}. Approximate extrema and area use numerical samples.")
                with st.expander("Calculation details"):
                    st.write("The derivative is calculated symbolically. Roots are found symbolically where possible, then checked numerically for sign changes. Extrema and signed area are estimated over the selected range.")
        export_rows = [
            {"function": label, "x": xx, "y": yy if valid else np.nan}
            for label, analysis in result["series"]
            for xx, yy, valid in zip(analysis["x"], analysis["y"], analysis["valid"])
        ]
        st.download_button("Download plotted values (CSV)", csv_bytes(pd.DataFrame(export_rows)),
                           "graph_data.csv", "text/csv")
        if fig is not None:
            st.download_button("Download graph (HTML)", html_bytes(fig), "graph.html", "text/html")

if result and result["kind"] == "data" and plot_kind == "Data" and dataset_view:
    frame, info = dataset_view["frame"], dataset_view["info"]
    with st.container(border=True):
        st.subheader("Dataset summary")
        st.write(info["prose"])
        st.caption(f"Showing a {dataset_view['chart'].lower()} chart. Change the chart type or columns above to explore another view.")
        with st.expander("How the summary is calculated"):
            st.write("Column types are inferred from their values. Numeric summaries use available numeric cells; missing values are counted separately. The correlation note uses paired numeric rows and describes association only.")
        if not info["numeric_summary"].empty:
            st.markdown("**Numeric columns**")
            st.dataframe(info["numeric_summary"], width="stretch", hide_index=True, alt="Summary statistics for numeric columns")
        if not info["date_summary"].empty:
            st.markdown("**Date and time columns**")
            st.dataframe(info["date_summary"], width="stretch", hide_index=True, alt="Date ranges and missing values")
        if not info["category_summary"].empty:
            st.markdown("**Text and category columns**")
            st.dataframe(info["category_summary"], width="stretch", hide_index=True, alt="Unique counts and common values for categorical columns")
        st.markdown("**Data preview**")
        st.dataframe(frame.head(30), width="stretch", hide_index=True, alt="First 30 rows of the dataset")
        data_col, graph_col_download = st.columns(2)
        with data_col:
            st.download_button("Download data (CSV)", csv_bytes(frame), "graph_data.csv", "text/csv", width="stretch")
        with graph_col_download:
            st.download_button("Download graph (HTML)", html_bytes(dataset_view["fig"]), "graph.html", "text/html", width="stretch")

if st.session_state.history:
    with st.expander("Recent functions"):
        st.write("\n".join(st.session_state.history))
