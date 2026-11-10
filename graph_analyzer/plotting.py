"""Interactive chart construction."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def function_figure(series, xmin, xmax, title="Function plot"):
    fig = go.Figure()
    for label, result in series:
        fig.add_trace(go.Scatter(x=result["x"], y=np.where(result["valid"], result["y"], np.nan),
                                 mode="lines", name=label, connectgaps=False))
    fig.update_layout(title=title, hovermode="x unified",
                      xaxis_title="x", yaxis_title="y", legend_title="Functions",
                      margin=dict(l=20, r=20, t=50, b=20))
    fig.update_xaxes(showgrid=True, zeroline=True, range=[xmin, xmax])
    fig.update_yaxes(showgrid=True, zeroline=True)
    return fig


def data_figure(x, y, label, analysis):
    fig = go.Figure(go.Scatter(x=x, y=y, mode="markers", name="Observations",
                               hovertemplate="x=%{x}<br>y=%{y}<extra></extra>"))
    if analysis["predicted"] is not None:
        order = np.argsort(x)
        fig.add_trace(go.Scatter(x=x[order], y=analysis["predicted"][order], mode="lines", name="Linear fit"))
    fig.update_layout(title=label, hovermode="closest",
                      xaxis_title="X", yaxis_title="Y", margin=dict(l=20, r=20, t=50, b=20))
    return fig


def dataset_figure(frame: pd.DataFrame, info: dict, chart: str, xcol=None, ycol=None,
                   colorcol=None, thirdcol=None):
    """Build common chart types from arbitrary tabular columns."""
    data = frame.copy()
    for col in info["numeric"]:
        data[col] = info["converted"][col]
    for col in info["dates"]:
        data[col] = info["converted"][col]

    if chart == "Line":
        if xcol is None:
            raise ValueError("A line chart needs a date or X column.")
        if ycol == "Row count":
            counts = data.dropna(subset=[xcol]).groupby(xcol).size().rename("Rows").reset_index()
            fig = px.line(counts, x=xcol, y="Rows", markers=True, title=f"Rows over {xcol}")
            fig.update_layout(hovermode="x unified", margin=dict(l=20, r=20, t=55, b=20))
            return fig
        if ycol is None:
            raise ValueError("Choose a numeric Y column.")
        data = data.dropna(subset=[xcol, ycol]).sort_values(xcol)
        fig = px.line(data, x=xcol, y=ycol, color=colorcol if colorcol != xcol else None,
                      markers=True, title=f"{ycol} over {xcol}")
    elif chart == "Scatter":
        if xcol is None or ycol is None:
            raise ValueError("A scatter plot needs two numeric columns.")
        data = data.dropna(subset=[xcol, ycol])
        fig = px.scatter(data, x=xcol, y=ycol, color=colorcol, title=f"{ycol} vs {xcol}")
        if colorcol is None and len(data) > 2 and data[xcol].nunique() > 1:
            fit = np.polyfit(data[xcol].to_numpy(dtype=float), data[ycol].to_numpy(dtype=float), 1)
            line_x = np.linspace(data[xcol].min(), data[xcol].max(), 100)
            fig.add_trace(go.Scatter(x=line_x, y=fit[0] * line_x + fit[1], mode="lines", name="Linear fit"))
    elif chart == "Bar":
        if xcol is None:
            raise ValueError("A bar chart needs a category column.")
        if ycol is None or ycol == xcol:
            counts = data[xcol].dropna().astype(str).value_counts().head(30).rename_axis(xcol).reset_index(name="Count")
            fig = px.bar(counts, x=xcol, y="Count", title=f"Count by {xcol}")
        else:
            grouped = data[[xcol, ycol]].dropna().groupby(xcol, as_index=False)[ycol].mean()
            grouped = grouped.sort_values(ycol, ascending=False).head(50)
            fig = px.bar(grouped, x=xcol, y=ycol, title=f"Average {ycol} by {xcol}")
    elif chart == "Histogram":
        if xcol is None:
            raise ValueError("A histogram needs a numeric column.")
        fig = px.histogram(data.dropna(subset=[xcol]), x=xcol, color=colorcol,
                           title=f"Distribution of {xcol}")
    elif chart == "Box":
        if ycol is None:
            raise ValueError("A box plot needs a numeric column.")
        fig = px.box(data.dropna(subset=[ycol]), x=xcol, y=ycol,
                     title=f"Distribution of {ycol}" + (f" by {xcol}" if xcol else ""))
    elif chart == "Pie":
        if xcol is None:
            raise ValueError("A pie chart needs a category column.")
        if ycol is None or ycol == xcol:
            counts = data[xcol].dropna().astype(str).value_counts().head(15).rename_axis(xcol).reset_index(name="Count")
            fig = px.pie(counts, names=xcol, values="Count", title=f"Share by {xcol}")
        else:
            grouped = data[[xcol, ycol]].dropna().groupby(xcol, as_index=False)[ycol].sum()
            grouped = grouped.nlargest(15, ycol)
            if (grouped[ycol] < 0).any() or grouped[ycol].sum() <= 0:
                raise ValueError("A pie chart needs non-negative values with a positive total. Try a bar chart instead.")
            fig = px.pie(grouped, names=xcol, values=ycol, title=f"{ycol} by {xcol}")
    elif chart == "Correlation":
        columns = info["numeric"]
        if len(columns) < 2:
            raise ValueError("A correlation matrix needs at least two numeric columns.")
        matrix = data[columns].corr()
        fig = go.Figure(go.Heatmap(z=matrix.to_numpy(), x=list(matrix.columns), y=list(matrix.index),
                                   zmin=-1, zmax=1, colorscale="RdBu", reversescale=True,
                                   colorbar_title="r", hovertemplate="%{y} vs %{x}<br>r=%{z:.3f}<extra></extra>"))
        fig.update_layout(title="Correlation between numeric columns")
    elif chart == "3D scatter":
        if xcol is None or ycol is None or thirdcol is None:
            raise ValueError("A 3D scatter plot needs three numeric columns.")
        fig = px.scatter_3d(data.dropna(subset=[xcol, ycol, thirdcol]), x=xcol, y=ycol, z=thirdcol,
                            color=colorcol, title=f"{xcol}, {ycol}, and {thirdcol}")
    else:
        raise ValueError(f"Unsupported chart type: {chart}")

    fig.update_layout(hovermode="closest", margin=dict(l=20, r=20, t=55, b=20),
                      legend_title_text="Group")
    return fig
