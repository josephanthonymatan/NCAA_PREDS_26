from __future__ import annotations

import json
import math
import random
from pathlib import Path

import pandas as pd

from .constants import DEFAULT_SEASON, FINAL_FOUR_PAIRINGS, LOGISTIC_K, REGIONS
from .paths import output_dir, processed_dir


ROUND_COLUMNS = ["R64", "R32", "Sweet16", "Elite8", "Final4", "Championship", "Champion"]
MATCHUP_ROUNDS = ["R64", "R32", "Sweet16", "Elite8", "Final4", "Championship"]
ROUND_SORT_ORDER = {round_name: index for index, round_name in enumerate(MATCHUP_ROUNDS)}


def _win_probability(rating_a: float, rating_b: float, k: float = LOGISTIC_K) -> float:
    return 1.0 / (1.0 + math.exp(-k * (rating_a - rating_b)))


def _simulate_game(team_a: str, team_b: str, ratings: dict[str, float], rng: random.Random) -> str:
    probability_a = _win_probability(ratings[team_a], ratings[team_b])
    return team_a if rng.random() < probability_a else team_b


def _record_matchup(
    round_name: str,
    team_a: str,
    team_b: str,
    winner: str,
    matchup_stats: dict[str, dict[tuple[str, str], dict[str, int]]],
) -> None:
    pair = tuple(sorted((team_a, team_b)))
    bucket = matchup_stats.setdefault(round_name, {})
    entry = bucket.setdefault(pair, {"matchup_count": 0})
    entry["matchup_count"] += 1
    entry[winner] = entry.get(winner, 0) + 1


def _simulate_round(
    games: list[tuple[str, str]],
    round_name: str,
    advancement_column: str,
    ratings: dict[str, float],
    advancements: dict[str, dict[str, int]],
    matchup_stats: dict[str, dict[tuple[str, str], dict[str, int]]],
    rng: random.Random,
) -> list[str]:
    winners: list[str] = []
    for team_a, team_b in games:
        winner = _simulate_game(team_a, team_b, ratings, rng)
        _record_matchup(round_name, team_a, team_b, winner, matchup_stats)
        winners.append(winner)
    for winner in winners:
        advancements[winner][advancement_column] += 1
    return winners


def _pairwise(teams: list[str]) -> list[tuple[str, str]]:
    return [(teams[index], teams[index + 1]) for index in range(0, len(teams), 2)]


def _simulate_region(
    region_games: list[tuple[str, str]],
    ratings: dict[str, float],
    advancements: dict[str, dict[str, int]],
    matchup_stats: dict[str, dict[tuple[str, str], dict[str, int]]],
    rng: random.Random,
) -> str:
    for team_a, team_b in region_games:
        advancements[team_a]["R64"] += 1
        advancements[team_b]["R64"] += 1

    winners_r32 = _simulate_round(region_games, "R64", "R32", ratings, advancements, matchup_stats, rng)
    winners_s16 = _simulate_round(_pairwise(winners_r32), "R32", "Sweet16", ratings, advancements, matchup_stats, rng)
    winners_e8 = _simulate_round(_pairwise(winners_s16), "Sweet16", "Elite8", ratings, advancements, matchup_stats, rng)
    region_champion = _simulate_round([(winners_e8[0], winners_e8[1])], "Elite8", "Final4", ratings, advancements, matchup_stats, rng)[0]
    return region_champion


def _simulate_final_four(
    regional_champs: dict[str, str],
    final_four_pairings: tuple[tuple[str, str], tuple[str, str]] | list[list[str]] | list[tuple[str, str]],
    ratings: dict[str, float],
    advancements: dict[str, dict[str, int]],
    matchup_stats: dict[str, dict[tuple[str, str], dict[str, int]]],
    rng: random.Random,
) -> str:
    left_a, left_b = final_four_pairings[0]
    right_a, right_b = final_four_pairings[1]

    finalist_one = _simulate_round(
        [(regional_champs[left_a], regional_champs[left_b])],
        "Final4",
        "Championship",
        ratings,
        advancements,
        matchup_stats,
        rng,
    )[0]
    finalist_two = _simulate_round(
        [(regional_champs[right_a], regional_champs[right_b])],
        "Final4",
        "Championship",
        ratings,
        advancements,
        matchup_stats,
        rng,
    )[0]
    champion = _simulate_round(
        [(finalist_one, finalist_two)],
        "Championship",
        "Champion",
        ratings,
        advancements,
        matchup_stats,
        rng,
    )[0]
    return champion


def _build_matchup_summary(
    matchup_stats: dict[str, dict[tuple[str, str], dict[str, int]]],
    display_lookup: dict[str, str],
    sims: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for round_name, bucket in matchup_stats.items():
        for pair, entry in bucket.items():
            ordered_pair = tuple(sorted(pair, key=lambda team_id: display_lookup.get(team_id, team_id)))
            team_a_id, team_b_id = ordered_pair
            matchup_count = int(entry["matchup_count"])
            team_a_wins = int(entry.get(team_a_id, 0))
            team_b_wins = int(entry.get(team_b_id, 0))
            rows.append(
                {
                    "round": round_name,
                    "team_a_id_canon": team_a_id,
                    "team_a_name": display_lookup.get(team_a_id, team_a_id),
                    "team_b_id_canon": team_b_id,
                    "team_b_name": display_lookup.get(team_b_id, team_b_id),
                    "matchup_count": matchup_count,
                    "matchup_pct": (matchup_count / sims) * 100.0,
                    "team_a_wins": team_a_wins,
                    "team_b_wins": team_b_wins,
                    "team_a_win_pct_when_met": (team_a_wins / matchup_count) * 100.0,
                    "team_b_win_pct_when_met": (team_b_wins / matchup_count) * 100.0,
                    "simulation_count": sims,
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=[
                "round",
                "team_a_id_canon",
                "team_a_name",
                "team_b_id_canon",
                "team_b_name",
                "matchup_count",
                "matchup_pct",
                "team_a_wins",
                "team_b_wins",
                "team_a_win_pct_when_met",
                "team_b_win_pct_when_met",
                "simulation_count",
            ]
        )

    summary = pd.DataFrame(rows)
    return summary.sort_values(
        ["round", "matchup_count", "team_a_name", "team_b_name"],
        ascending=[True, False, True, True],
        key=lambda column: column.map(ROUND_SORT_ORDER) if column.name == "round" else column,
    ).reset_index(drop=True)


def simulate_bracket_details(
    bracket_round64: pd.DataFrame,
    first_four: pd.DataFrame,
    ratings_table: pd.DataFrame,
    sims: int = 100000,
    seed: int = 42,
    final_four_pairings: tuple[tuple[str, str], tuple[str, str]] | list[list[str]] | list[tuple[str, str]] = FINAL_FOUR_PAIRINGS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    ratings_lookup = ratings_table.set_index("team_id_canon")["blended_elo_scale"].to_dict()
    display_lookup = ratings_table.set_index("team_id_canon")["Team"].to_dict()

    participants = set()
    for column in ("team_top", "team_bottom"):
        if column in bracket_round64.columns:
            participants.update(str(value) for value in bracket_round64[column].dropna())
    if not first_four.empty:
        participants.update(str(value) for value in first_four["team_a_id_canon"].dropna())
        participants.update(str(value) for value in first_four["team_b_id_canon"].dropna())

    missing_ratings = sorted(participants.difference(ratings_lookup))
    if missing_ratings:
        raise ValueError(f"Missing ratings for tournament teams: {missing_ratings}")

    rng = random.Random(seed)
    advancements = {team_id: {column: 0 for column in ROUND_COLUMNS} for team_id in participants}
    matchup_stats: dict[str, dict[tuple[str, str], dict[str, int]]] = {round_name: {} for round_name in MATCHUP_ROUNDS}

    region_games = {
        region: bracket_round64[bracket_round64["region"] == region].sort_values("matchup_order")
        for region in REGIONS
    }
    first_four_games = first_four.sort_values(["region", "seed"]).to_dict("records") if not first_four.empty else []

    for _ in range(sims):
        first_four_winners: dict[str, str] = {}
        for game in first_four_games:
            winner = _simulate_game(game["team_a_id_canon"], game["team_b_id_canon"], ratings_lookup, rng)
            first_four_winners[str(game["group_id"])] = winner

        regional_champs: dict[str, str] = {}
        for region, frame in region_games.items():
            resolved_games: list[tuple[str, str]] = []
            for row in frame.to_dict("records"):
                top = row["team_top"] if pd.notna(row["team_top"]) else first_four_winners[str(row["play_in_group_top"])]
                bottom = row["team_bottom"] if pd.notna(row["team_bottom"]) else first_four_winners[str(row["play_in_group_bottom"])]
                resolved_games.append((str(top), str(bottom)))
            regional_champs[region] = _simulate_region(resolved_games, ratings_lookup, advancements, matchup_stats, rng)
        _simulate_final_four(regional_champs, final_four_pairings, ratings_lookup, advancements, matchup_stats, rng)

    results = (
        pd.DataFrame.from_dict(advancements, orient="index")
        .reset_index()
        .rename(columns={"index": "team_id_canon"})
    )
    results["Team"] = results["team_id_canon"].map(display_lookup)
    results["simulation_count"] = sims
    ordered_columns = ["team_id_canon", "Team", *ROUND_COLUMNS, "simulation_count"]
    results = results[ordered_columns]
    results = results.sort_values(["Champion", "Championship", "Final4", "Elite8", "Sweet16", "R32", "R64"], ascending=False)
    matchup_summary = _build_matchup_summary(matchup_stats, display_lookup, sims)
    return results, matchup_summary


def simulate_bracket(
    bracket_round64: pd.DataFrame,
    first_four: pd.DataFrame,
    ratings_table: pd.DataFrame,
    sims: int = 100000,
    seed: int = 42,
    final_four_pairings: tuple[tuple[str, str], tuple[str, str]] | list[list[str]] | list[tuple[str, str]] = FINAL_FOUR_PAIRINGS,
) -> pd.DataFrame:
    results, _ = simulate_bracket_details(
        bracket_round64=bracket_round64,
        first_four=first_four,
        ratings_table=ratings_table,
        sims=sims,
        seed=seed,
        final_four_pairings=final_four_pairings,
    )
    return results


def simulate_tournament(
    season: int = DEFAULT_SEASON,
    sims: int = 100000,
    seed: int = 42,
    processed_root: Path | None = None,
    output_root: Path | None = None,
) -> Path:
    processed_root = processed_root or processed_dir(season)
    output_root = output_root or output_dir(season)

    ratings = pd.read_csv(output_root / "combined_ratings.csv")
    bracket_round64 = pd.read_csv(processed_root / "bracket_round64.csv")
    first_four_path = processed_root / "first_four.csv"
    first_four = pd.read_csv(first_four_path) if first_four_path.exists() else pd.DataFrame()
    final_four_pairings = FINAL_FOUR_PAIRINGS
    if (processed_root / "bracket_metadata.json").exists():
        metadata = json.loads((processed_root / "bracket_metadata.json").read_text(encoding="utf-8"))
        metadata_pairings = metadata.get("final_four_pairings")
        if metadata_pairings:
            final_four_pairings = metadata_pairings

    results, matchup_summary = simulate_bracket_details(
        bracket_round64,
        first_four,
        ratings,
        sims=sims,
        seed=seed,
        final_four_pairings=final_four_pairings,
    )
    output_path = output_root / "monte_carlo_tourney_results.csv"
    results.to_csv(output_path, index=False)
    matchup_summary.to_csv(output_root / "matchup_summary.csv", index=False)
    return output_path
