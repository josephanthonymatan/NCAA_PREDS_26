from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from .constants import BRACKET_REPORT_FILE, DEFAULT_SEASON, FINAL_FOUR_PAIRINGS
from .html_tables import clean_numeric, extract_html_tables, find_table, normalize_header
from .naming import canonical_team_id, normalize_team_name
from .paths import ensure_directories, manual_dir, processed_dir, raw_dir, report_path
from .report import metadata_as_json, parse_report_file


def _find_existing_file(directory: Path, *candidates: str) -> Path:
    for candidate in candidates:
        path = directory / candidate
        if path.exists():
            return path
    raise FileNotFoundError(f"Unable to find any of {candidates} in {directory}")


def _looks_like_challenge_page(path: Path) -> bool:
    if not path.exists() or path.suffix.lower() not in {".html", ".htm"}:
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    return "Just a moment..." in text or "Enable JavaScript and cookies to continue" in text


def _clean_team_column(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().replace({"nan": pd.NA})


def _find_column(frame: pd.DataFrame, candidates: set[str]) -> str:
    normalized = {normalize_header(column): column for column in frame.columns}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    for candidate in candidates:
        for normalized_name, original_name in normalized.items():
            if normalized_name.startswith(candidate) or candidate in normalized_name:
                return original_name
    raise ValueError(f"Unable to find any of {sorted(candidates)} in {list(frame.columns)}")


def _read_html_table(path: Path, required_headers: set[str]) -> pd.DataFrame:
    return find_table(extract_html_tables(path.read_text(encoding="utf-8")), required_headers)


def _parse_elo(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path)
    else:
        frame = _read_html_table(path, {"team", "elo"})
    team_col = _find_column(frame, {"team"})
    elo_col = _find_column(frame, {"elo"})
    parsed = pd.DataFrame(
        {
            "team_name": _clean_team_column(frame[team_col]),
            "elo": clean_numeric(frame[elo_col]),
        }
    )
    return parsed.dropna(subset=["team_name", "elo"]).drop_duplicates(subset=["team_name"])


def _parse_ap_poll(path: Path, prefix: str) -> pd.DataFrame:
    raw_text = path.read_text(encoding="utf-8")
    if "College Poll Archive" in raw_text:
        return _parse_college_poll_archive(raw_text, prefix)
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path)
    else:
        frame = find_table(extract_html_tables(raw_text), {"team", "rank"})
    team_col = _find_column(frame, {"team"})
    rank_col = _find_column(frame, {"rank"})
    points_col = next(
        (column for column in frame.columns if normalize_header(column) in {"pts", "points"}),
        None,
    )
    fpv_col = next(
        (column for column in frame.columns if normalize_header(column) in {"fpv", "firstplacevotes"}),
        None,
    )
    parsed = pd.DataFrame(
        {
            "team_name": _clean_team_column(frame[team_col]),
            f"{prefix}_rank": clean_numeric(frame[rank_col]),
        }
    )
    team_with_fpv = parsed["team_name"].astype(str)
    fpv_matches = team_with_fpv.str.extract(r"^(?P<team>.*?)\s*\((?P<fpv>\d+)\)\s*$")
    has_embedded_fpv = fpv_matches["team"].notna()
    if has_embedded_fpv.any():
        parsed.loc[has_embedded_fpv, "team_name"] = fpv_matches.loc[has_embedded_fpv, "team"].str.strip()
        parsed[f"{prefix}_fpv"] = clean_numeric(fpv_matches["fpv"])
    if points_col is not None:
        parsed[f"{prefix}_points"] = clean_numeric(frame[points_col])
    if fpv_col is not None:
        parsed[f"{prefix}_fpv"] = clean_numeric(frame[fpv_col])
    parsed = parsed[parsed[f"{prefix}_rank"].between(1, 25, inclusive="both")]
    return parsed.dropna(subset=["team_name"]).drop_duplicates(subset=["team_name"])


def _parse_college_poll_archive(html: str, prefix: str) -> pd.DataFrame:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        raise ValueError("Unable to locate College Poll Archive table")

    rows: list[dict[str, object]] = []
    for tr in table.find_all("tr"):
        cells = [" ".join(cell.stripped_strings).strip() for cell in tr.find_all("td")]
        if len(cells) < 7:
            continue
        rank, _, _, team_with_fpv, _conference, _record, points = cells[:7]
        team_name = team_with_fpv
        fpv = None
        match = re.match(r"^(.*?)\s+\((\d+)\)$", team_with_fpv)
        if match:
            team_name = match.group(1).strip()
            fpv = int(match.group(2))
        rows.append(
            {
                "team_name": team_name,
                f"{prefix}_rank": rank,
                f"{prefix}_points": points,
                f"{prefix}_fpv": fpv,
            }
        )

    parsed = pd.DataFrame(rows)
    parsed[f"{prefix}_rank"] = clean_numeric(parsed[f"{prefix}_rank"])
    parsed[f"{prefix}_points"] = clean_numeric(parsed[f"{prefix}_points"])
    if f"{prefix}_fpv" in parsed:
        parsed[f"{prefix}_fpv"] = clean_numeric(parsed[f"{prefix}_fpv"])
    parsed = parsed[parsed[f"{prefix}_rank"].between(1, 25, inclusive="both")]
    return parsed.dropna(subset=["team_name"]).drop_duplicates(subset=["team_name"])


def _parse_torvik_json(path: Path) -> pd.DataFrame:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not rows:
        raise ValueError("Torvik payload is empty")
    if isinstance(rows[0], dict):
        frame = pd.DataFrame(rows)
        team_col = _find_column(frame, {"team", "teamname", "name"})
        eff_col = _find_column(frame, {"adjem", "netrtg", "rating"})
        parsed = pd.DataFrame(
            {
                "team_name": _clean_team_column(frame[team_col]),
                "efficiency_rating": clean_numeric(frame[eff_col]),
            }
        )
        return parsed.dropna(subset=["team_name", "efficiency_rating"]).drop_duplicates(subset=["team_name"])
    schema_path = path.with_name(path.stem + "_schema.json")
    if schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        team_index = int(schema["team_index"])
        eff_index = int(schema["efficiency_index"])
        parsed = pd.DataFrame(
            {
                "team_name": [row[team_index] for row in rows],
                "efficiency_rating": [row[eff_index] for row in rows],
            }
        )
        parsed["efficiency_rating"] = clean_numeric(parsed["efficiency_rating"])
        return parsed.dropna(subset=["team_name", "efficiency_rating"]).drop_duplicates(subset=["team_name"])
    parsed = pd.DataFrame(
        {
            "team_name": [row[1] for row in rows],
            "efficiency_rating": [row[10] for row in rows],
        }
    )
    parsed["efficiency_rating"] = clean_numeric(parsed["efficiency_rating"])
    return parsed.dropna(subset=["team_name", "efficiency_rating"]).drop_duplicates(subset=["team_name"])


def _parse_efficiency(path: Path) -> tuple[pd.DataFrame, str]:
    if path.suffix.lower() == ".json":
        return _parse_torvik_json(path), "torvik"
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path)
    else:
        frame = _read_html_table(path, {"team"})
    team_col = _find_column(frame, {"team"})
    eff_col = _find_column(frame, {"netrtg", "adjem", "rating"})
    parsed = pd.DataFrame(
        {
            "team_name": _clean_team_column(frame[team_col]),
            "efficiency_rating": clean_numeric(frame[eff_col]),
        }
    )
    return parsed.dropna(subset=["team_name", "efficiency_rating"]).drop_duplicates(subset=["team_name"]), "kenpom"


def _load_alias_overrides(path: Path) -> dict[tuple[str, str], str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("source,source_name,team_id_canon,display_name\n", encoding="utf-8")
        return {}
    frame = pd.read_csv(path).fillna("")
    overrides: dict[tuple[str, str], str] = {}
    for _, row in frame.iterrows():
        source = str(row.get("source", "")).strip().lower()
        source_name = str(row.get("source_name", "")).strip()
        target = str(row.get("team_id_canon", "")).strip()
        if source and source_name and target:
            overrides[(source, normalize_team_name(source_name))] = target
    return overrides


def _resolve_source_ids(
    frame: pd.DataFrame,
    source_name: str,
    bracket_lookup: dict[str, str],
    overrides: dict[tuple[str, str], str],
) -> pd.DataFrame:
    mapped = frame.copy()
    normalized_names = mapped["team_name"].map(normalize_team_name)

    def assign_team_id(index: int) -> str:
        raw_name = normalized_names.iloc[index]
        override_key = (source_name, raw_name)
        if override_key in overrides:
            return overrides[override_key]
        if raw_name in bracket_lookup:
            return bracket_lookup[raw_name]
        return canonical_team_id(str(mapped.iloc[index]["team_name"]))

    mapped["team_id_canon"] = [assign_team_id(i) for i in range(len(mapped))]
    return mapped


def _dedupe_source(frame: pd.DataFrame, source_prefix: str) -> pd.DataFrame:
    rename_map = {"team_name": f"name_{source_prefix}"}
    return frame.rename(columns=rename_map).drop_duplicates(subset=["team_id_canon"])


def prepare_datasets(
    season: int = DEFAULT_SEASON,
    raw_root: Path | None = None,
    processed_root: Path | None = None,
    manual_root: Path | None = None,
    report_file: Path | None = None,
) -> dict[str, Path]:
    ensure_directories(season)
    raw_root = raw_root or raw_dir(season)
    processed_root = processed_root or processed_dir(season)
    manual_root = manual_root or manual_dir(season)
    report_file = report_file or report_path(BRACKET_REPORT_FILE[season])
    processed_root.mkdir(parents=True, exist_ok=True)
    manual_root.mkdir(parents=True, exist_ok=True)

    bracket_field, bracket_round64, first_four, bracket_meta = parse_report_file(report_file, season=season)

    elo_path = _find_existing_file(raw_root, "elo.html", "elo.csv")
    latest_ap_path = _find_existing_file(raw_root, "ap_latest.html", "ap_latest.csv")
    preseason_ap_path = _find_existing_file(raw_root, "ap_preseason.html", "ap_preseason.csv")
    selected_efficiency = raw_root / "efficiency_source.selected"
    if selected_efficiency.exists():
        source_name = selected_efficiency.read_text(encoding="utf-8").strip()
        if source_name == "torvik":
            efficiency_path = _find_existing_file(raw_root, "torvik.json", "torvik.csv")
        else:
            efficiency_path = _find_existing_file(raw_root, "kenpom.html", "kenpom.csv", "torvik.json", "torvik.csv")
    else:
        efficiency_path = _find_existing_file(raw_root, "kenpom.html", "kenpom.csv", "torvik.json", "torvik.csv")
    if _looks_like_challenge_page(efficiency_path):
        efficiency_path = _find_existing_file(raw_root, "torvik.json", "torvik.csv")

    elo = _parse_elo(elo_path)
    ap_latest = _parse_ap_poll(latest_ap_path, "ap_latest")
    ap_preseason = _parse_ap_poll(preseason_ap_path, "ap_preseason")
    efficiency, efficiency_source = _parse_efficiency(efficiency_path)

    overrides = _load_alias_overrides(manual_root / "team_alias_overrides.csv")
    bracket_lookup = {
        normalize_team_name(name): team_id
        for name, team_id in bracket_field[["team_name_bracket", "team_id_canon"]].drop_duplicates().itertuples(index=False)
    }

    elo = _resolve_source_ids(elo, "elo", bracket_lookup, overrides)
    efficiency = _resolve_source_ids(efficiency, "efficiency", bracket_lookup, overrides)
    ap_latest = _resolve_source_ids(ap_latest, "ap_latest", bracket_lookup, overrides)
    ap_preseason = _resolve_source_ids(ap_preseason, "ap_preseason", bracket_lookup, overrides)

    bracket_names = bracket_field[["team_id_canon", "team_name_bracket"]].drop_duplicates()
    base_ids = sorted(
        set(bracket_names["team_id_canon"])
        | set(elo["team_id_canon"])
        | set(efficiency["team_id_canon"])
    )
    base = pd.DataFrame({"team_id_canon": base_ids})
    base = base.merge(bracket_names, on="team_id_canon", how="left")
    base = base.merge(_dedupe_source(elo, "elo"), on="team_id_canon", how="left")
    base = base.merge(_dedupe_source(efficiency, "efficiency"), on="team_id_canon", how="left")
    base = base.merge(_dedupe_source(ap_latest, "ap_latest"), on="team_id_canon", how="left")
    base = base.merge(_dedupe_source(ap_preseason, "ap_preseason"), on="team_id_canon", how="left")

    if "ap_latest_points" in ap_latest.columns:
        base = base.merge(
            ap_latest[["team_id_canon", "ap_latest_points"]].drop_duplicates("team_id_canon"),
            on="team_id_canon",
            how="left",
        )
    if "ap_latest_fpv" in ap_latest.columns:
        base = base.merge(
            ap_latest[["team_id_canon", "ap_latest_fpv"]].drop_duplicates("team_id_canon"),
            on="team_id_canon",
            how="left",
        )
    if "ap_preseason_points" in ap_preseason.columns:
        base = base.merge(
            ap_preseason[["team_id_canon", "ap_preseason_points"]].drop_duplicates("team_id_canon"),
            on="team_id_canon",
            how="left",
        )
    if "ap_preseason_fpv" in ap_preseason.columns:
        base = base.merge(
            ap_preseason[["team_id_canon", "ap_preseason_fpv"]].drop_duplicates("team_id_canon"),
            on="team_id_canon",
            how="left",
        )

    base["Team"] = (
        base[["team_name_bracket", "name_elo", "name_efficiency", "name_ap_latest", "name_ap_preseason"]]
        .bfill(axis=1)
        .iloc[:, 0]
    )
    base["season"] = season
    base["efficiency_source"] = efficiency_source

    team_aliases = base[
        [
            "team_id_canon",
            "Team",
            "team_name_bracket",
            "name_elo",
            "name_efficiency",
            "name_ap_latest",
            "name_ap_preseason",
        ]
    ].rename(columns={"team_name_bracket": "name_bracket"})

    ratings_inputs = base[
        [
            "season",
            "team_id_canon",
            "Team",
            "elo",
            "efficiency_rating",
            "ap_latest_rank",
            "ap_preseason_rank",
            "efficiency_source",
        ]
    ].copy()

    bracket_team_ids = set(bracket_names["team_id_canon"])
    join_qa = ratings_inputs[ratings_inputs["team_id_canon"].isin(bracket_team_ids)].copy()
    join_qa["has_elo"] = join_qa["elo"].notna()
    join_qa["has_efficiency"] = join_qa["efficiency_rating"].notna()
    join_qa["has_ap_latest"] = join_qa["ap_latest_rank"].notna()
    join_qa["has_ap_preseason"] = join_qa["ap_preseason_rank"].notna()
    join_qa["needs_override"] = ~(join_qa["has_elo"] & join_qa["has_efficiency"])
    join_qa = join_qa[
        [
            "team_id_canon",
            "Team",
            "has_elo",
            "has_efficiency",
            "has_ap_latest",
            "has_ap_preseason",
            "needs_override",
        ]
    ]

    bracket_round64 = bracket_round64.copy()
    bracket_round64["season"] = season
    bracket_round64["team_top_name"] = bracket_round64["team_top"]
    bracket_round64["team_bottom_name"] = bracket_round64["team_bottom"]
    bracket_round64["team_top"] = bracket_round64["team_top"].map(
        lambda value: canonical_team_id(str(value)) if pd.notna(value) else None
    )
    bracket_round64["team_bottom"] = bracket_round64["team_bottom"].map(
        lambda value: canonical_team_id(str(value)) if pd.notna(value) else None
    )
    if not first_four.empty:
        first_four = first_four.copy()
        first_four["season"] = season
        for column in ("team_a", "team_b"):
            first_four[f"{column}_id_canon"] = first_four[column].map(canonical_team_id)

    bracket_meta["final_four_pairings"] = list(FINAL_FOUR_PAIRINGS)
    bracket_meta["efficiency_source"] = efficiency_source

    outputs = {
        "bracket_field": processed_root / "bracket_field_68.csv",
        "bracket_round64": processed_root / "bracket_round64.csv",
        "first_four": processed_root / "first_four.csv",
        "team_aliases": processed_root / "team_aliases.csv",
        "ratings_inputs": processed_root / "ratings_inputs.csv",
        "join_qa": processed_root / "join_qa.csv",
        "bracket_metadata": processed_root / "bracket_metadata.json",
    }
    bracket_field.to_csv(outputs["bracket_field"], index=False)
    bracket_round64.to_csv(outputs["bracket_round64"], index=False)
    first_four.to_csv(outputs["first_four"], index=False)
    team_aliases.to_csv(outputs["team_aliases"], index=False)
    ratings_inputs.to_csv(outputs["ratings_inputs"], index=False)
    join_qa.to_csv(outputs["join_qa"], index=False)
    outputs["bracket_metadata"].write_text(metadata_as_json(bracket_meta), encoding="utf-8")
    return outputs
