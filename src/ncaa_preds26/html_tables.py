from __future__ import annotations

import re

import pandas as pd
from bs4 import BeautifulSoup


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())


def extract_html_tables(html: str) -> list[pd.DataFrame]:
    soup = BeautifulSoup(html, "html.parser")
    frames: list[pd.DataFrame] = []
    for table in soup.find_all("table"):
        header_rows: list[list[str]] = []
        rows: list[list[str]] = []
        header: list[str] | None = None
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if not cells:
                continue
            values = [" ".join(cell.stripped_strings).strip() for cell in cells]
            if not any(values):
                continue
            if header is None and tr.find_all("th") and not tr.find_all("td"):
                header_rows.append(values)
                continue
            if header is None:
                header = header_rows[-1] if header_rows else [f"column_{index}" for index in range(len(values))]
            if len(values) < len(header):
                values += [""] * (len(header) - len(values))
            elif len(values) > len(header):
                values = values[: len(header)]
            rows.append(values)
        if header is None and header_rows:
            header = header_rows[-1]
        if header is not None and rows:
            frames.append(pd.DataFrame(rows, columns=header))
    return frames


def find_table(frames: list[pd.DataFrame], required_headers: set[str]) -> pd.DataFrame:
    required = {normalize_header(value) for value in required_headers}
    for frame in frames:
        headers = {normalize_header(value) for value in frame.columns}
        if required.issubset(headers):
            return frame.copy()
    raise ValueError(f"Unable to find HTML table with headers {sorted(required_headers)}")


def clean_numeric(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace(r"[^0-9.\-]+", "", regex=True)
        .replace("", pd.NA)
    )
    return pd.to_numeric(cleaned, errors="coerce")
