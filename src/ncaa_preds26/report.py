from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from .constants import REGIONS
from .naming import canonical_team_id


ENTITY_PATTERN = re.compile(r'entity\[[^\]]*?"[^"]+","([^"]+)"[^\]]*?\]')
CITE_PATTERN = re.compile(r"cite[^]+")
OTHER_MARKUP_PATTERN = re.compile(r"[^]+")


def _clean_report_text(text: str) -> str:
    text = ENTITY_PATTERN.sub(lambda match: match.group(1), text)
    text = CITE_PATTERN.sub("", text)
    text = OTHER_MARKUP_PATTERN.sub("", text)
    return text


def _parse_matchup_line(region: str, matchup_order: int, line: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    pattern = re.compile(
        r"^\((?P<seed_top>\d+)\)\s+(?P<top>.+?)\s+vs\s+\((?P<seed_bottom>\d+)\)\s+(?P<bottom>.+?)(?:\s+\*\((?P<note>.+)\)\*)?$"
    )
    match = pattern.match(line.strip())
    if match is None:
        raise ValueError(f"Unable to parse bracket line: {line}")

    seed_top = int(match.group("seed_top"))
    seed_bottom = int(match.group("seed_bottom"))
    team_top = match.group("top").strip()
    team_bottom = match.group("bottom").strip()
    note = (match.group("note") or "").strip()

    first_four_rows: list[dict[str, object]] = []
    row: dict[str, object] = {
        "region": region,
        "matchup_order": matchup_order,
        "seed_top": seed_top,
        "team_top": team_top,
        "seed_bottom": seed_bottom,
        "team_bottom": team_bottom,
        "play_in_group_top": None,
        "play_in_group_bottom": None,
        "note": note or None,
    }

    for side in ("top", "bottom"):
        team_text = row[f"team_{side}"]
        if isinstance(team_text, str) and "/" in team_text and "First Four matchup" in note:
            teams = [part.strip() for part in team_text.split("/") if part.strip()]
            if len(teams) != 2:
                raise ValueError(f"Expected two First Four teams in line: {line}")
            group_id = f"{region.lower()}_{row[f'seed_{side}']}_{matchup_order}_{side}"
            row[f"team_{side}"] = None
            row[f"play_in_group_{side}"] = group_id
            first_four_rows.append(
                {
                    "group_id": group_id,
                    "region": region,
                    "seed": int(row[f"seed_{side}"]),
                    "slot_side": side,
                    "team_a": teams[0],
                    "team_b": teams[1],
                }
            )
    return row, first_four_rows


def parse_report_bracket(report_text: str, season: int = 2026) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    cleaned = _clean_report_text(report_text)
    lines = [line.strip() for line in cleaned.splitlines()]

    current_region: str | None = None
    matchup_order = 0
    round64_rows: list[dict[str, object]] = []
    first_four_rows: list[dict[str, object]] = []

    for line in lines:
        if not line:
            continue
        if line.startswith("### ") and line.endswith(" region"):
            region_name = line.removeprefix("### ").removesuffix(" region")
            if region_name not in REGIONS:
                current_region = None
                continue
            current_region = region_name
            matchup_order = 0
            continue
        if current_region is None or not line.startswith("("):
            continue
        matchup_order += 1
        row, groups = _parse_matchup_line(current_region, matchup_order, line)
        round64_rows.append(row)
        first_four_rows.extend(groups)

    round64 = pd.DataFrame(
        round64_rows,
        columns=[
            "region",
            "matchup_order",
            "seed_top",
            "team_top",
            "seed_bottom",
            "team_bottom",
            "play_in_group_top",
            "play_in_group_bottom",
            "note",
        ],
    )
    first_four = pd.DataFrame(
        first_four_rows,
        columns=["group_id", "region", "seed", "slot_side", "team_a", "team_b"],
    )

    field_rows: list[dict[str, object]] = []
    for _, row in round64.iterrows():
        for side in ("top", "bottom"):
            team_name = row[f"team_{side}"]
            play_in_group = row[f"play_in_group_{side}"]
            seed = int(row[f"seed_{side}"])
            if pd.notna(team_name):
                field_rows.append(
                    {
                        "season": season,
                        "region": row["region"],
                        "matchup_order": int(row["matchup_order"]),
                        "slot_side": side,
                        "seed": seed,
                        "team_name_bracket": str(team_name),
                        "team_id_canon": canonical_team_id(str(team_name)),
                        "play_in_group": None,
                    }
                )
            if pd.notna(play_in_group):
                group_rows = first_four[first_four["group_id"] == play_in_group]
                for team_column in ("team_a", "team_b"):
                    team_name = str(group_rows.iloc[0][team_column])
                    field_rows.append(
                        {
                            "season": season,
                            "region": row["region"],
                            "matchup_order": int(row["matchup_order"]),
                            "slot_side": side,
                            "seed": seed,
                            "team_name_bracket": team_name,
                            "team_id_canon": canonical_team_id(team_name),
                            "play_in_group": play_in_group,
                        }
                    )
        note = str(row.get("note") or "")
        resolved_match = re.search(r"First Four winner over (.+)", note)
        if resolved_match:
            loser_name = resolved_match.group(1).strip()
            field_rows.append(
                {
                    "season": season,
                    "region": row["region"],
                    "matchup_order": int(row["matchup_order"]),
                    "slot_side": "bottom",
                    "seed": int(row["seed_bottom"]),
                    "team_name_bracket": loser_name,
                    "team_id_canon": canonical_team_id(loser_name),
                    "play_in_group": f"resolved_{str(row['region']).lower()}_{int(row['seed_bottom'])}_{int(row['matchup_order'])}_bottom",
                }
            )

    field = pd.DataFrame(field_rows).drop_duplicates(subset=["team_id_canon"]).sort_values(
        ["region", "seed", "team_name_bracket"]
    )

    host_city_match = re.search(
        r"\*\*Final Four host city shown on the official bracket:\*\*\s*([^.\n]+)",
        cleaned,
    )
    metadata = {
        "season": season,
        "source": "research_report",
        "report_sections": list(REGIONS),
        "host_city": host_city_match.group(1).strip() if host_city_match else None,
        "unresolved_first_four_games": int(len(first_four)),
    }
    return field.reset_index(drop=True), round64.reset_index(drop=True), first_four.reset_index(drop=True), metadata


def parse_report_file(path: Path, season: int = 2026) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    return parse_report_bracket(path.read_text(encoding="utf-8"), season=season)


def metadata_as_json(metadata: dict[str, object]) -> str:
    return json.dumps(metadata, indent=2, sort_keys=True)
