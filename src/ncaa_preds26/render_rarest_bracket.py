from __future__ import annotations

import hashlib
import json
import math
import random
from html import escape
from pathlib import Path
from textwrap import dedent

import pandas as pd

from .constants import DEFAULT_SEASON, FINAL_FOUR_PAIRINGS, REGIONS
from .paths import output_dir, processed_dir
from .pixel_icon import pixel_basketball_icon_data_url
from .simulate import _win_probability


ROUND_LABELS = {
    "FirstFour": "First Four",
    "R64": "Round of 64",
    "R32": "Round of 32",
    "Sweet16": "Sweet 16",
    "Elite8": "Elite 8",
    "Final4": "Final Four",
    "Championship": "Championship",
}
ROUND_ORDER = ("R64", "R32", "Sweet16", "Elite8")


def _pairwise(teams: list[str]) -> list[tuple[str, str]]:
    return [(teams[index], teams[index + 1]) for index in range(0, len(teams), 2)]


def _team_lookup(
    bracket_round64: pd.DataFrame,
    first_four: pd.DataFrame,
    ratings: pd.DataFrame,
) -> dict[str, dict[str, object]]:
    team_meta: dict[str, dict[str, object]] = {}
    for row in bracket_round64.to_dict("records"):
        if pd.notna(row.get("team_top")):
            team_meta[str(row["team_top"])] = {
                "name": str(row["team_top_name"]),
                "seed": int(row["seed_top"]),
                "region": str(row["region"]),
            }
        if pd.notna(row.get("team_bottom")):
            team_meta[str(row["team_bottom"])] = {
                "name": str(row["team_bottom_name"]),
                "seed": int(row["seed_bottom"]),
                "region": str(row["region"]),
            }
    if not first_four.empty:
        for row in first_four.to_dict("records"):
            team_meta[str(row["team_a_id_canon"])] = {
                "name": str(row["team_a"]),
                "seed": int(row["seed"]),
                "region": str(row["region"]),
            }
            team_meta[str(row["team_b_id_canon"])] = {
                "name": str(row["team_b"]),
                "seed": int(row["seed"]),
                "region": str(row["region"]),
            }

    rating_lookup = ratings.set_index("team_id_canon").to_dict("index")
    for team_id, meta in team_meta.items():
        rating_row = rating_lookup[team_id]
        meta["elo"] = round(float(rating_row["elo"]), 1)
        meta["model_rating"] = round(float(rating_row["blended_elo_scale"]), 1)
    return team_meta


def _simulate_game_card(
    round_name: str,
    region: str,
    slot_label: str,
    team_a: str,
    team_b: str,
    team_lookup: dict[str, dict[str, object]],
    ratings_lookup: dict[str, float],
    rng: random.Random,
) -> dict[str, object]:
    probability_a = _win_probability(ratings_lookup[team_a], ratings_lookup[team_b])
    probability_b = 1.0 - probability_a
    favorite = team_a if probability_a >= probability_b else team_b
    if rng.random() < probability_a:
        winner = team_a
        loser = team_b
        winner_probability = probability_a
    else:
        winner = team_b
        loser = team_a
        winner_probability = probability_b

    winner_meta = team_lookup[winner]
    loser_meta = team_lookup[loser]
    favorite_meta = team_lookup[favorite]
    return {
        "round": round_name,
        "round_label": ROUND_LABELS[round_name],
        "region": region,
        "slot_label": slot_label,
        "winner_id": winner,
        "winner_name": str(winner_meta["name"]),
        "winner_seed": int(winner_meta["seed"]),
        "winner_elo": float(winner_meta["elo"]),
        "loser_id": loser,
        "loser_name": str(loser_meta["name"]),
        "loser_seed": int(loser_meta["seed"]),
        "loser_elo": float(loser_meta["elo"]),
        "winner_probability": winner_probability * 100.0,
        "favorite_name": str(favorite_meta["name"]),
        "favorite_probability": max(probability_a, probability_b) * 100.0,
        "is_upset": winner != favorite,
    }


def _format_odds_label(log10_probability: float) -> str:
    inverse_log10 = -log10_probability
    if inverse_log10 < 6:
        probability = 10 ** log10_probability
        return f"1 in {round(1 / probability):,}"
    if inverse_log10 < 12:
        probability = 10 ** log10_probability
        return f"1 in {(1 / probability):.2e}"
    return f"1 in 10^{inverse_log10:.1f}"


def _render_game_card(game: dict[str, object], compact: bool = False) -> str:
    upset_class = " game-card--upset" if game["is_upset"] else ""
    compact_class = " game-card--compact" if compact else ""
    return f"""
      <article class="game-card{upset_class}{compact_class}">
        <div class="game-head">
          <span>{escape(str(game["round_label"]))}</span>
          <span>{escape(str(game["slot_label"]))}</span>
        </div>
        <div class="team-lane team-lane--winner">
          <span class="seed">{int(game["winner_seed"])}</span>
          <strong>{escape(str(game["winner_name"]))}</strong>
          <span class="elo">Elo {float(game["winner_elo"]):.1f}</span>
        </div>
        <div class="team-lane">
          <span class="seed">{int(game["loser_seed"])}</span>
          <span class="loser-name">{escape(str(game["loser_name"]))}</span>
          <span class="elo">Elo {float(game["loser_elo"]):.1f}</span>
        </div>
        <div class="prob-line">
          <span>Winner chance</span>
          <strong>{float(game["winner_probability"]):.1f}%</strong>
        </div>
      </article>
    """


def _render_region_panel(region: dict[str, object], mirrored: bool = False) -> str:
    round_order = tuple(reversed(ROUND_ORDER)) if mirrored else ROUND_ORDER
    region_columns = []
    for round_name in round_order:
        cards = "".join(_render_game_card(game) for game in region["rounds"][round_name])
        region_columns.append(f'<div class="round-column" data-round="{round_name}">{cards}</div>')
    board_class = "region-board region-board--mirrored" if mirrored else "region-board region-board--standard"
    return f"""
      <section class="region-panel">
        <div class="region-title">
          <span>{escape(str(region["name"]))} sector</span>
          <h2>{escape(str(region["name"]))}</h2>
        </div>
        <div class="{board_class}">
          {''.join(region_columns)}
        </div>
      </section>
    """


def _simulate_rarest_bracket(
    season: int,
    sims: int,
    seed: int,
    processed_root: Path,
    output_root: Path,
) -> dict[str, object]:
    bracket_round64 = pd.read_csv(processed_root / "bracket_round64.csv")
    first_four_path = processed_root / "first_four.csv"
    first_four = pd.read_csv(first_four_path) if first_four_path.exists() else pd.DataFrame()
    ratings = pd.read_csv(output_root / "combined_ratings.csv")
    metadata_path = processed_root / "bracket_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}

    team_lookup = _team_lookup(bracket_round64, first_four, ratings)
    ratings_lookup = ratings.set_index("team_id_canon")["blended_elo_scale"].to_dict()
    region_frames = {
        region: bracket_round64[bracket_round64["region"] == region].sort_values("matchup_order").to_dict("records")
        for region in REGIONS
    }
    final_four_pairings = metadata.get("final_four_pairings", [list(pairing) for pairing in FINAL_FOUR_PAIRINGS])
    host_city = str(metadata.get("host_city", "Indianapolis"))

    first_four_games = first_four.sort_values(["region", "seed"]).to_dict("records") if not first_four.empty else []
    rng = random.Random(seed)
    signature_counts: dict[str, int] = {}
    rarest_run: dict[str, object] | None = None

    for simulation_index in range(1, sims + 1):
        log_probability = 0.0
        signature_winners: list[str] = []
        all_games: list[dict[str, object]] = []
        first_four_cards: list[dict[str, object]] = []
        first_four_winners: dict[str, str] = {}

        for row in first_four_games:
            card = _simulate_game_card(
                round_name="FirstFour",
                region=str(row["region"]),
                slot_label=f"{row['region']} {int(row['seed'])} play-in",
                team_a=str(row["team_a_id_canon"]),
                team_b=str(row["team_b_id_canon"]),
                team_lookup=team_lookup,
                ratings_lookup=ratings_lookup,
                rng=rng,
            )
            first_four_cards.append(card)
            first_four_winners[str(row["group_id"])] = str(card["winner_id"])
            signature_winners.append(str(card["winner_id"]))
            all_games.append(card)
            log_probability += math.log(float(card["winner_probability"]) / 100.0)

        region_payload: list[dict[str, object]] = []
        regional_champs: dict[str, str] = {}
        for region in REGIONS:
            round_payload: dict[str, list[dict[str, object]]] = {round_name: [] for round_name in ROUND_ORDER}
            resolved_r64: list[tuple[str, str]] = []
            for row in region_frames[region]:
                top = str(row["team_top"]) if pd.notna(row.get("team_top")) else first_four_winners[str(row["play_in_group_top"])]
                bottom = (
                    str(row["team_bottom"]) if pd.notna(row.get("team_bottom")) else first_four_winners[str(row["play_in_group_bottom"])]
                )
                resolved_r64.append((top, bottom))

            winners_previous_round: list[str] = []
            current_games = resolved_r64
            for round_name in ROUND_ORDER:
                winners_current_round: list[str] = []
                round_cards: list[dict[str, object]] = []
                for game_index, (team_a, team_b) in enumerate(current_games, start=1):
                    card = _simulate_game_card(
                        round_name=round_name,
                        region=region,
                        slot_label=f"G{game_index}",
                        team_a=team_a,
                        team_b=team_b,
                        team_lookup=team_lookup,
                        ratings_lookup=ratings_lookup,
                        rng=rng,
                    )
                    winners_current_round.append(str(card["winner_id"]))
                    round_cards.append(card)
                    all_games.append(card)
                    signature_winners.append(str(card["winner_id"]))
                    log_probability += math.log(float(card["winner_probability"]) / 100.0)
                round_payload[round_name] = round_cards
                winners_previous_round = winners_current_round
                current_games = _pairwise(winners_previous_round) if len(winners_previous_round) > 1 else []

            regional_champs[region] = str(round_payload["Elite8"][0]["winner_id"])
            region_payload.append({"name": region, "rounds": round_payload})

        final_four_cards: list[dict[str, object]] = []
        semifinal_one = _simulate_game_card(
            round_name="Final4",
            region="Final Four",
            slot_label=f"{final_four_pairings[0][0]} vs {final_four_pairings[0][1]}",
            team_a=regional_champs[str(final_four_pairings[0][0])],
            team_b=regional_champs[str(final_four_pairings[0][1])],
            team_lookup=team_lookup,
            ratings_lookup=ratings_lookup,
            rng=rng,
        )
        semifinal_two = _simulate_game_card(
            round_name="Final4",
            region="Final Four",
            slot_label=f"{final_four_pairings[1][0]} vs {final_four_pairings[1][1]}",
            team_a=regional_champs[str(final_four_pairings[1][0])],
            team_b=regional_champs[str(final_four_pairings[1][1])],
            team_lookup=team_lookup,
            ratings_lookup=ratings_lookup,
            rng=rng,
        )
        championship_card = _simulate_game_card(
            round_name="Championship",
            region="Championship",
            slot_label=host_city,
            team_a=str(semifinal_one["winner_id"]),
            team_b=str(semifinal_two["winner_id"]),
            team_lookup=team_lookup,
            ratings_lookup=ratings_lookup,
            rng=rng,
        )

        for card in (semifinal_one, semifinal_two, championship_card):
            final_four_cards.append(card) if card["round"] == "Final4" else None
            all_games.append(card)
            signature_winners.append(str(card["winner_id"]))
            log_probability += math.log(float(card["winner_probability"]) / 100.0)

        signature_hash = hashlib.sha1("|".join(signature_winners).encode("utf-8")).hexdigest()
        signature_counts[signature_hash] = signature_counts.get(signature_hash, 0) + 1

        if rarest_run is None or log_probability < float(rarest_run["log_probability"]):
            wildest_games = sorted(all_games, key=lambda game: float(game["winner_probability"]))
            rarest_run = {
                "simulation_index": simulation_index,
                "signature_hash": signature_hash,
                "log_probability": log_probability,
                "log10_probability": log_probability / math.log(10),
                "first_four": first_four_cards,
                "regions": region_payload,
                "final_four": [semifinal_one, semifinal_two],
                "championship": championship_card,
                "wildest_games": wildest_games[:6],
                "upset_count": sum(1 for game in all_games if bool(game["is_upset"])),
                "deep_upset_count": sum(1 for game in all_games if float(game["winner_probability"]) <= 35.0),
            }

    assert rarest_run is not None
    rarest_run["sample_occurrence_count"] = int(signature_counts[str(rarest_run["signature_hash"])])
    rarest_run["sample_occurrence_pct"] = (int(rarest_run["sample_occurrence_count"]) / sims) * 100.0
    rarest_run["unique_bracket_count"] = len(signature_counts)
    rarest_run["season"] = season
    rarest_run["simulation_count"] = sims
    rarest_run["seed"] = seed
    rarest_run["host_city"] = host_city
    rarest_run["final_four_pairings"] = final_four_pairings
    rarest_run["champion_name"] = str(rarest_run["championship"]["winner_name"])
    rarest_run["champion_seed"] = int(rarest_run["championship"]["winner_seed"])
    rarest_run["odds_label"] = _format_odds_label(float(rarest_run["log10_probability"]))
    return rarest_run


def render_rarest_bracket(
    season: int = DEFAULT_SEASON,
    sims: int = 100000,
    seed: int = 42,
    processed_root: Path | None = None,
    output_root: Path | None = None,
    destination: Path | None = None,
) -> Path:
    processed_root = processed_root or processed_dir(season)
    output_root = output_root or output_dir(season)
    destination = destination or (output_root / f"most_unlikely_bracket_{season}.html")
    favicon_url = pixel_basketball_icon_data_url()

    payload = _simulate_rarest_bracket(season=season, sims=sims, seed=seed, processed_root=processed_root, output_root=output_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    json_path = destination.with_suffix(".json")
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    regions_by_name = {str(region["name"]): region for region in payload["regions"]}
    left_regions = [str(payload["final_four_pairings"][0][0]), str(payload["final_four_pairings"][1][0])]
    right_regions = [str(payload["final_four_pairings"][0][1]), str(payload["final_four_pairings"][1][1])]
    first_four_markup = ""
    if payload["first_four"]:
        cards = "".join(_render_game_card(game, compact=True) for game in payload["first_four"])
        first_four_markup = f"""
          <section class="mini-strip">
            <div class="panel-title">
              <span class="eyebrow">First Four</span>
              <h2>Play-in results inside this bracket</h2>
            </div>
            <div class="mini-grid">{cards}</div>
          </section>
        """

    wildest_markup = "".join(
        f"""
          <li>
            <strong>{escape(str(game["winner_name"]))}</strong> over {escape(str(game["loser_name"]))}
            <span>{escape(str(game["round_label"]))} · {float(game["winner_probability"]):.1f}% winner chance</span>
          </li>
        """
        for game in payload["wildest_games"]
    )

    document = dedent(
        f"""
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>{season} Most Unlikely Bracket</title>
          <link rel="icon" type="image/svg+xml" href="{favicon_url}">
          <link rel="preconnect" href="https://fonts.googleapis.com">
          <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
          <link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@400;500;600;700&family=Silkscreen:wght@400;700&display=swap" rel="stylesheet">
          <style>
            :root {{
              --bg: oklch(16% 0.03 245);
              --cabinet: oklch(29% 0.05 34);
              --screen: oklch(94% 0.03 86);
              --screen-alt: oklch(91% 0.03 84);
              --ink: oklch(24% 0.04 240);
              --muted: oklch(47% 0.03 238);
              --gold: oklch(82% 0.13 90);
              --teal: oklch(74% 0.13 190);
              --coral: oklch(69% 0.16 28);
              --outline: oklch(22% 0.04 241);
              --shadow: rgba(9, 16, 28, 0.22);
            }}

            * {{
              box-sizing: border-box;
            }}

            body {{
              margin: 0;
              min-height: 100vh;
              font-family: "Chakra Petch", sans-serif;
              color: var(--ink);
              background:
                radial-gradient(circle at top, color-mix(in oklch, var(--coral) 16%, transparent), transparent 36%),
                linear-gradient(180deg, color-mix(in oklch, var(--cabinet) 78%, var(--bg)) 0%, var(--bg) 100%);
              padding: clamp(0.7rem, 1.5vw, 1.25rem);
            }}

            body::before {{
              content: "";
              position: fixed;
              inset: 0;
              pointer-events: none;
              background: repeating-linear-gradient(180deg, rgba(255,255,255,0) 0 5px, rgba(17,24,39,0.07) 5px 7px);
              mix-blend-mode: multiply;
              opacity: 0.62;
            }}

            .cabinet {{
              max-width: 1700px;
              margin: 0 auto;
              border: 6px solid color-mix(in oklch, var(--gold) 24%, var(--outline));
              background: linear-gradient(180deg, color-mix(in oklch, var(--cabinet) 84%, var(--gold) 16%), var(--cabinet));
              padding: clamp(0.8rem, 1.4vw, 1.15rem);
              box-shadow: 0 24px 60px var(--shadow);
            }}

            .screen {{
              border: 5px solid var(--outline);
              background: linear-gradient(180deg, color-mix(in oklch, var(--screen) 90%, var(--gold) 10%), var(--screen));
              padding: clamp(0.85rem, 1.5vw, 1.2rem);
            }}

            h1, h2, p {{
              margin: 0;
            }}

            .eyebrow,
            .panel-title span,
            .region-title span,
            .game-head,
            .metric-label {{
              font-family: "Silkscreen", monospace;
              text-transform: uppercase;
              letter-spacing: 0.12em;
              font-size: 0.63rem;
            }}

            .hero {{
              display: grid;
              grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.8fr);
              align-items: end;
              gap: 0.45rem;
              margin-bottom: 0.85rem;
            }}

            .hero h1 {{
              grid-column: 1;
              font-family: "Silkscreen", monospace;
              font-size: clamp(1.6rem, 2.65vw, 2.45rem);
              line-height: 0.98;
              max-width: 15ch;
            }}

            .hero p {{
              max-width: 78ch;
              font-size: 0.98rem;
              color: color-mix(in oklch, var(--ink) 82%, var(--muted) 18%);
            }}

            .hero > .eyebrow {{
              grid-column: 1 / -1;
            }}

            .hero > p:last-child {{
              grid-column: 2;
              max-width: 38ch;
              padding-bottom: 0.18rem;
            }}

            .summary-grid {{
              display: grid;
              grid-template-columns: repeat(4, minmax(0, 1fr));
              gap: 0.75rem;
              margin-bottom: 1rem;
            }}

            .metric-card,
            .notes-panel,
            .mini-strip,
            .region-panel,
            .center-panel {{
              border: 4px solid var(--outline);
              background: color-mix(in oklch, var(--screen) 92%, var(--screen-alt) 8%);
              box-shadow: 6px 6px 0 rgba(17, 24, 39, 0.12);
            }}

            .metric-card {{
              padding: 0.75rem;
              display: grid;
              gap: 0.35rem;
            }}

            .metric-card strong {{
              font-size: clamp(1rem, 1.8vw, 1.45rem);
              line-height: 1;
            }}

            .metric-card p {{
              font-size: 0.86rem;
              color: color-mix(in oklch, var(--ink) 82%, var(--muted) 18%);
            }}

            .analysis-grid {{
              display: grid;
              grid-template-columns: minmax(0, 1.5fr) minmax(280px, 0.8fr);
              gap: 0.85rem;
              margin-bottom: 1rem;
            }}

            .notes-panel,
            .mini-strip,
            .center-panel,
            .region-panel {{
              padding: 0.8rem;
            }}

            .panel-title {{
              display: grid;
              gap: 0.2rem;
              margin-bottom: 0.7rem;
            }}

            .notes-panel ul {{
              margin: 0;
              padding-left: 1rem;
              display: grid;
              gap: 0.45rem;
            }}

            .notes-panel--wildest ul {{
              grid-template-columns: repeat(2, minmax(0, 1fr));
              column-gap: 1rem;
            }}

            .notes-panel li span {{
              display: block;
              color: var(--muted);
              font-size: 0.85rem;
              margin-top: 0.15rem;
            }}

            .mini-grid {{
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
              gap: 0.7rem;
            }}

            .main-bracket {{
              display: grid;
              grid-template-columns: minmax(0, 1fr) 228px minmax(0, 1fr);
              gap: 0.75rem;
              align-items: stretch;
            }}

            .side-stack {{
              display: grid;
              grid-template-rows: repeat(2, minmax(0, 1fr));
              gap: 0.9rem;
            }}

            .region-panel {{
              display: grid;
              gap: 0.7rem;
            }}

            .region-title {{
              display: grid;
              gap: 0.18rem;
            }}

            .region-title h2,
            .panel-title h2 {{
              font-family: "Silkscreen", monospace;
              font-size: 1rem;
            }}

            .region-board {{
              --card-height: 152px;
              --lane-gap: 8px;
              display: grid;
              grid-template-columns: repeat(4, minmax(136px, 1fr));
              gap: 0.5rem;
              overflow: visible;
            }}

            .round-column {{
              position: relative;
              display: grid;
              gap: var(--round-gap, var(--lane-gap));
              padding-top: var(--round-offset, 0px);
              align-content: start;
            }}

            .round-column[data-round="R64"] {{
              --round-offset: 0px;
              --round-gap: var(--lane-gap);
            }}

            .round-column[data-round="R32"] {{
              --round-offset: calc((var(--card-height) + var(--lane-gap)) / 2);
              --round-gap: calc(var(--card-height) + (var(--lane-gap) * 2));
            }}

            .round-column[data-round="Sweet16"] {{
              --round-offset: calc(((var(--card-height) + var(--lane-gap)) * 3) / 2);
              --round-gap: calc((var(--card-height) * 3) + (var(--lane-gap) * 4));
            }}

            .round-column[data-round="Elite8"] {{
              --round-offset: calc(((var(--card-height) + var(--lane-gap)) * 7) / 2);
              --round-gap: 0px;
            }}

            .center-panel {{
              display: grid;
              grid-template-rows: auto auto;
              align-content: center;
              gap: 0.55rem;
            }}

            .center-stage {{
              display: grid;
              grid-template-rows: repeat(3, auto);
              gap: 0.55rem;
              align-content: center;
            }}

            .center-slot {{
              display: flex;
              justify-content: center;
            }}

            .center-slot .game-card {{
              width: min(100%, 208px);
            }}

            .game-card {{
              position: relative;
              border: 3px solid var(--outline);
              background: color-mix(in oklch, var(--screen-alt) 92%, white 8%);
              padding: 0.42rem;
              height: var(--card-height, 152px);
              display: grid;
              gap: 0.28rem;
              align-content: start;
            }}

            .game-card--upset {{
              background: color-mix(in oklch, var(--coral) 14%, var(--screen));
            }}

            .game-card--compact {{
              height: auto;
              min-height: 126px;
            }}

            .game-head {{
              display: flex;
              justify-content: space-between;
              gap: 0.35rem;
              color: var(--muted);
            }}

            .team-lane {{
              display: grid;
              grid-template-columns: 1.45rem minmax(0, 1fr);
              grid-template-areas:
                "seed name"
                "seed elo";
              gap: 0.08rem 0.32rem;
              align-items: start;
              padding: 0.14rem 0;
            }}

            .team-lane--winner {{
              border: 3px solid color-mix(in oklch, var(--teal) 56%, var(--outline));
              background: color-mix(in oklch, var(--gold) 52%, var(--screen));
              padding: 0.3rem;
            }}

            .seed {{
              grid-area: seed;
              font-family: "Silkscreen", monospace;
              font-size: 0.6rem;
              padding-top: 0.12rem;
            }}

            .team-lane strong,
            .loser-name {{
              grid-area: name;
              min-width: 0;
              font-size: 0.78rem;
              line-height: 1.05;
              overflow-wrap: anywhere;
            }}

            .elo {{
              grid-area: elo;
              font-size: 0.64rem;
              color: color-mix(in oklch, var(--ink) 76%, var(--muted) 24%);
            }}

            .prob-line {{
              margin-top: auto;
              padding-top: 0.22rem;
              border-top: 2px solid color-mix(in oklch, var(--outline) 35%, transparent);
              display: flex;
              justify-content: space-between;
              gap: 0.6rem;
              font-size: 0.68rem;
              line-height: 1.1;
            }}

            .prob-line strong {{
              font-size: 0.76rem;
            }}

            .footer-note {{
              margin-top: 1rem;
              padding-top: 0.55rem;
              border-top: 2px solid color-mix(in oklch, var(--outline) 24%, transparent);
              font-size: 0.86rem;
              line-height: 1.35;
              color: color-mix(in oklch, var(--ink) 74%, var(--muted) 26%);
            }}

            @media (max-width: 1280px) {{
              .hero {{
                grid-template-columns: minmax(0, 1.05fr) minmax(250px, 0.95fr);
              }}

              .hero h1 {{
                font-size: clamp(1.45rem, 2.45vw, 2.05rem);
                max-width: 14ch;
              }}

              .analysis-grid {{
                grid-template-columns: minmax(0, 1.3fr) minmax(0, 0.9fr);
              }}

              .main-bracket {{
                grid-template-columns: minmax(0, 1fr) 212px minmax(0, 1fr);
                gap: 0.65rem;
              }}

              .region-board {{
                --card-height: 148px;
                grid-template-columns: repeat(4, minmax(124px, 1fr));
              }}
            }}

            @media (max-width: 1140px) {{
              .hero,
              .analysis-grid,
              .main-bracket {{
                grid-template-columns: 1fr;
              }}

              .hero h1,
              .hero > p:last-child,
              .hero > .eyebrow {{
                grid-column: 1;
              }}

              .hero h1 {{
                max-width: 14ch;
              }}

              .hero > p:last-child {{
                max-width: 70ch;
                padding-bottom: 0;
              }}

              .summary-grid {{
                grid-template-columns: repeat(2, minmax(0, 1fr));
              }}

              .notes-panel--wildest ul {{
                grid-template-columns: 1fr;
              }}

              .side-stack {{
                grid-template-rows: none;
              }}
            }}

            @media (max-width: 900px) {{
              body {{
                padding: 0.45rem;
              }}

              .screen {{
                padding: 0.7rem;
              }}

              .summary-grid {{
                grid-template-columns: 1fr;
                gap: 0.6rem;
              }}

              .region-board {{
                grid-template-columns: 1fr;
              }}

              .round-column {{
                gap: 0.7rem;
                padding-top: 0;
              }}

              .region-board .round-column::before,
              .region-board .round-column::after,
              .region-board .game-card::before,
              .region-board .game-card::after {{
                display: none;
              }}

              .game-card,
              .center-slot .game-card {{
                height: auto;
                min-height: 0;
              }}
            }}
          </style>
        </head>
        <body>
          <main class="cabinet">
            <section class="screen">
              <header class="hero">
                <p class="eyebrow">{season} bracket meta-analysis</p>
                <h1>I replayed {payload["simulation_count"]:,} saved simulations and kept the least likely full bracket.</h1>
                <p>I score each simulated bracket by multiplying the win probability of every game that actually happened. Lower path probability means a less likely bracket.</p>
              </header>

              <section class="summary-grid">
                <article class="metric-card">
                  <span class="metric-label">Modeled path odds</span>
                  <strong>{escape(str(payload["odds_label"]))}</strong>
                  <p>I get this by multiplying every winning game probability in this one bracket.</p>
                </article>
                <article class="metric-card">
                  <span class="metric-label">Seen in sample</span>
                  <strong>{int(payload["sample_occurrence_count"]):,} time</strong>
                  <p>{float(payload["sample_occurrence_pct"]):.3f}% of the {payload["simulation_count"]:,} sampled brackets matched this exact path.</p>
                </article>
                <article class="metric-card">
                  <span class="metric-label">Champion</span>
                  <strong>No. {int(payload["champion_seed"])} {escape(str(payload["champion_name"]))}</strong>
                  <p>I first saw this exact bracket on simulation #{int(payload["simulation_index"]):,}.</p>
                </article>
                <article class="metric-card">
                  <span class="metric-label">Upsets in bracket</span>
                  <strong>{int(payload["upset_count"])} upsets</strong>
                  <p>{int(payload["deep_upset_count"])} of those wins came from teams that started at 35% or worse.</p>
                </article>
              </section>

              <section class="analysis-grid">
                <section class="notes-panel notes-panel--wildest">
                  <div class="panel-title">
                    <span class="eyebrow">Lowest-probability games</span>
                    <h2>The games that made this bracket so unlikely</h2>
                  </div>
                  <ul>{wildest_markup}</ul>
                </section>
                <section class="notes-panel">
                  <div class="panel-title">
                    <span class="eyebrow">How I scored it</span>
                    <h2>How to read this page</h2>
                  </div>
                  <ul>
                    <li>
                      <strong>{int(payload["unique_bracket_count"]):,} unique full brackets</strong>
                      <span>I saw that many distinct complete bracket paths in the {payload["simulation_count"]:,}-run sample.</span>
                    </li>
                    <li>
                      <strong>Final Four mapping comes from the processed bracket metadata</strong>
                      <span>I use the same semifinal matchups and championship site as the main tournament simulation.</span>
                    </li>
                    <li>
                      <strong>Coral cards mark upsets</strong>
                      <span>I shade a game coral when the winner started below 50% win probability.</span>
                    </li>
                  </ul>
                </section>
              </section>

              {first_four_markup}

              <section class="main-bracket">
                <div class="side-stack">
                  {_render_region_panel(regions_by_name[left_regions[0]], mirrored=False)}
                  {_render_region_panel(regions_by_name[left_regions[1]], mirrored=False)}
                </div>
                <section class="center-panel">
                  <div class="panel-title">
                    <span class="eyebrow">Final rounds</span>
                    <h2>Semifinals and championship</h2>
                  </div>
                  <div class="center-stage">
                    <div class="center-slot center-slot--semi">{_render_game_card(payload["final_four"][0])}</div>
                    <div class="center-slot">{_render_game_card(payload["championship"])}</div>
                    <div class="center-slot center-slot--semi">{_render_game_card(payload["final_four"][1])}</div>
                  </div>
                </section>
                <div class="side-stack">
                  {_render_region_panel(regions_by_name[right_regions[0]], mirrored=True)}
                  {_render_region_panel(regions_by_name[right_regions[1]], mirrored=True)}
                </div>
              </section>

              <p class="footer-note">I saved the underlying data to {escape(str(json_path.name))}. Every probability on this page comes from the same local blended-rating game model used elsewhere in this repo.</p>
            </section>
          </main>
        </body>
        </html>
        """
    ).strip()

    destination.write_text(document, encoding="utf-8")
    return destination
