"""Data and self-contained HTML exports."""
from io import StringIO
import pandas as pd


def csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8")


def html_bytes(figure) -> bytes:
    return figure.to_html(full_html=True, include_plotlyjs=True).encode("utf-8")
