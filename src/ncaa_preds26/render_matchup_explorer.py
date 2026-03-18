from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pandas as pd

from .constants import DEFAULT_SEASON
from .paths import output_dir, processed_dir
from .pixel_icon import pixel_basketball_icon_data_url


ROUND_LABELS = {
    "FirstFour": "First Four",
    "R64": "Round of 64",
    "R32": "Round of 32",
    "Sweet16": "Sweet 16",
    "Elite8": "Elite 8",
    "Final4": "Final Four",
    "Championship": "Championship",
}
REGION_ORDER = ["East", "West", "South", "Midwest"]


def _source_from_slot(row: dict[str, object], team_key: str, play_in_key: str) -> dict[str, str]:
    if pd.notna(row.get(team_key)):
        return {"type": "team", "teamId": str(row[team_key])}
    if pd.notna(row.get(play_in_key)):
        return {"type": "game", "gameId": f"firstfour:{str(row[play_in_key])}"}
    raise ValueError(f"Missing bracket source for slot {team_key}/{play_in_key}")


def _region_layout(round_name: str, index: int) -> tuple[int, int, int]:
    if round_name == "R64":
        return 1, index + 1, 1
    if round_name == "R32":
        return 2, (index * 2) + 1, 2
    if round_name == "Sweet16":
        return 3, (index * 4) + 1, 4
    if round_name == "Elite8":
        return 4, 1, 8
    raise ValueError(f"Unsupported region round {round_name}")


def _load_payload(processed_root: Path, output_root: Path, season: int) -> dict[str, object]:
    round64 = pd.read_csv(processed_root / "bracket_round64.csv")
    first_four_path = processed_root / "first_four.csv"
    first_four = pd.read_csv(first_four_path) if first_four_path.exists() else pd.DataFrame()
    ratings = pd.read_csv(output_root / "combined_ratings.csv")
    results = pd.read_csv(output_root / "monte_carlo_tourney_results.csv")
    matchup_summary = pd.read_csv(output_root / "matchup_summary.csv")
    metadata_path = processed_root / "bracket_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}

    simulation_count = int(results["simulation_count"].dropna().iloc[0])
    title_rows = results[["Team", "Champion"]].copy()
    title_rows["champion_pct"] = (title_rows["Champion"] / simulation_count) * 100.0
    most_likely_row = title_rows.sort_values(["Champion", "Team"], ascending=[False, True]).iloc[0]
    least_likely_row = title_rows[title_rows["Champion"] > 0].sort_values(["Champion", "Team"], ascending=[True, True]).iloc[0]

    team_meta: dict[str, dict[str, object]] = {}
    for row in round64.to_dict("records"):
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

    tournament_team_ids = set(team_meta)
    tournament_ratings = ratings[ratings["team_id_canon"].isin(tournament_team_ids)].copy()

    teams = []
    for row in tournament_ratings.sort_values(["elo", "Team"], ascending=[False, True]).to_dict("records"):
        team_id = str(row["team_id_canon"])
        meta = team_meta[team_id]
        teams.append(
            {
                "team_id": team_id,
                "name": str(meta["name"]),
                "seed": int(meta["seed"]),
                "region": str(meta["region"]),
                "elo": round(float(row["elo"]), 1),
                "model_rating": round(float(row["blended_elo_scale"]), 1),
            }
        )

    games: dict[str, dict[str, object]] = {}
    game_order: list[str] = []
    play_in_ids: list[str] = []

    if not first_four.empty:
        for index, row in enumerate(first_four.sort_values(["region", "seed"]).to_dict("records"), start=1):
            game_id = f"firstfour:{row['group_id']}"
            games[game_id] = {
                "id": game_id,
                "round": "FirstFour",
                "region": str(row["region"]),
                "label": f"{row['region']} seed {int(row['seed'])} play-in",
                "slotA": {"type": "team", "teamId": str(row["team_a_id_canon"])},
                "slotB": {"type": "team", "teamId": str(row["team_b_id_canon"])},
                "order": index,
            }
            play_in_ids.append(game_id)
            game_order.append(game_id)

    region_payload: list[dict[str, object]] = []
    region_winner_games: dict[str, str] = {}
    for region in REGION_ORDER:
        region_rows = round64[round64["region"] == region].sort_values("matchup_order")
        if region_rows.empty:
            continue

        round_map: dict[str, list[str]] = {"R64": [], "R32": [], "Sweet16": [], "Elite8": []}

        for index, row in enumerate(region_rows.to_dict("records")):
            game_id = f"r64:{region.lower()}:{index + 1}"
            column, row_start, row_span = _region_layout("R64", index)
            games[game_id] = {
                "id": game_id,
                "round": "R64",
                "region": region,
                "column": column,
                "rowStart": row_start,
                "rowSpan": row_span,
                "slotA": _source_from_slot(row, "team_top", "play_in_group_top"),
                "slotB": _source_from_slot(row, "team_bottom", "play_in_group_bottom"),
            }
            round_map["R64"].append(game_id)
            game_order.append(game_id)

        previous_round = round_map["R64"]
        for round_name, size in (("R32", 4), ("Sweet16", 2), ("Elite8", 1)):
            current_ids: list[str] = []
            for index in range(size):
                game_id = f"{round_name.lower()}:{region.lower()}:{index + 1}"
                column, row_start, row_span = _region_layout(round_name, index)
                games[game_id] = {
                    "id": game_id,
                    "round": round_name,
                    "region": region,
                    "column": column,
                    "rowStart": row_start,
                    "rowSpan": row_span,
                    "slotA": {"type": "game", "gameId": previous_round[index * 2]},
                    "slotB": {"type": "game", "gameId": previous_round[(index * 2) + 1]},
                }
                current_ids.append(game_id)
                game_order.append(game_id)
            round_map[round_name] = current_ids
            previous_round = current_ids

        region_winner_games[region] = round_map["Elite8"][0]
        region_payload.append({"name": region, "games": round_map})

    final_four_pairings = metadata.get("final_four_pairings", [["East", "South"], ["Midwest", "West"]])
    final_four_ids: list[str] = []
    for index, pairing in enumerate(final_four_pairings, start=1):
        left_region, right_region = pairing
        game_id = f"final4:{index}"
        games[game_id] = {
            "id": game_id,
            "round": "Final4",
            "label": f"{left_region} vs {right_region}",
            "regions": [left_region, right_region],
            "slotA": {"type": "game", "gameId": region_winner_games[left_region]},
            "slotB": {"type": "game", "gameId": region_winner_games[right_region]},
        }
        final_four_ids.append(game_id)
        game_order.append(game_id)

    championship_id = "championship:1"
    games[championship_id] = {
        "id": championship_id,
        "round": "Championship",
        "label": str(metadata.get("host_city", "Indianapolis")),
        "slotA": {"type": "game", "gameId": final_four_ids[0]},
        "slotB": {"type": "game", "gameId": final_four_ids[1]},
    }
    game_order.append(championship_id)

    matchup_rows = matchup_summary.sort_values(["round", "team_a_id_canon", "team_b_id_canon"]).to_dict("records")
    return {
        "season": season,
        "simulationCount": simulation_count,
        "roundLabels": ROUND_LABELS,
        "finalFourPairings": final_four_pairings,
        "teams": teams,
        "games": games,
        "gameOrder": game_order,
        "playInIds": play_in_ids,
        "regions": region_payload,
        "finalFourIds": final_four_ids,
        "championshipId": championship_id,
        "matchups": matchup_rows,
        "hostCity": str(metadata.get("host_city", "Indianapolis")),
        "siteInsights": {
            "mostLikelyChampion": str(most_likely_row["Team"]),
            "mostLikelyChampionPct": round(float(most_likely_row["champion_pct"]), 1),
            "leastLikelyChampion": str(least_likely_row["Team"]),
            "leastLikelyChampionCount": int(least_likely_row["Champion"]),
        },
    }


def render_matchup_explorer(
    season: int = DEFAULT_SEASON,
    processed_root: Path | None = None,
    output_root: Path | None = None,
    destination: Path | None = None,
) -> Path:
    processed_root = processed_root or processed_dir(season)
    output_root = output_root or output_dir(season)
    destination = destination or (output_root / f"matchup_lab_{season}.html")

    matchup_summary_path = output_root / "matchup_summary.csv"
    if not matchup_summary_path.exists():
        raise FileNotFoundError(
            f"Missing matchup summary at {matchup_summary_path}. Run the simulation command again to generate matchup-level data."
        )

    payload = _load_payload(processed_root, output_root, season)
    github_url = "https://github.com/josephanthonymatan"
    github_handle = "@josephanthonymatan"
    x_url = "https://x.com/jam0xb797fd"
    x_handle = "@jam0xb797fd"
    favicon_url = pixel_basketball_icon_data_url()

    document = dedent(
        f"""
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>{season} Bracket Lab</title>
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
              --shadow: rgba(9, 16, 28, 0.24);
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
                radial-gradient(circle at top, color-mix(in oklch, var(--gold) 18%, transparent), transparent 34%),
                linear-gradient(180deg, color-mix(in oklch, var(--cabinet) 78%, var(--bg)) 0%, var(--bg) 100%);
              padding: clamp(0.75rem, 1.6vw, 1.4rem);
            }}

            body::before {{
              content: "";
              position: fixed;
              inset: 0;
              pointer-events: none;
              background: repeating-linear-gradient(180deg, rgba(255,255,255,0) 0 5px, rgba(17,24,39,0.07) 5px 7px);
              mix-blend-mode: multiply;
              opacity: 0.65;
            }}

            .cabinet {{
              max-width: 1680px;
              margin: 0 auto;
              border: 6px solid color-mix(in oklch, var(--gold) 24%, var(--outline));
              background: linear-gradient(180deg, color-mix(in oklch, var(--cabinet) 84%, var(--gold) 16%), var(--cabinet));
              padding: clamp(0.8rem, 1.4vw, 1.2rem);
              box-shadow: 0 24px 60px var(--shadow);
            }}

            .screen {{
              border: 5px solid var(--outline);
              background: linear-gradient(180deg, color-mix(in oklch, var(--screen) 90%, var(--gold) 10%), var(--screen));
              padding: clamp(0.85rem, 1.5vw, 1.2rem);
            }}

            h1, h2, h3, p {{
              margin: 0;
            }}

            .eyebrow,
            .region-title span,
            .matchup-head,
            .summary-label {{
              font-family: "Silkscreen", monospace;
              text-transform: uppercase;
              letter-spacing: 0.12em;
              font-size: 0.66rem;
            }}

            .hero {{
              display: grid;
              grid-template-columns: minmax(0, 1.08fr) minmax(320px, 0.92fr);
              gap: 0.55rem 1rem;
              align-items: end;
              margin-bottom: 0.9rem;
            }}

            .hero-top {{
              grid-column: 1 / -1;
              display: flex;
              justify-content: space-between;
              align-items: flex-start;
              gap: 0.9rem;
            }}

            .hero h1 {{
              grid-column: 1;
              font-family: "Silkscreen", monospace;
              font-size: clamp(1.65rem, 2.8vw, 2.55rem);
              line-height: 0.98;
              max-width: 13ch;
            }}

            .hero p {{
              grid-column: 2;
              max-width: 38ch;
              color: color-mix(in oklch, var(--ink) 82%, var(--muted) 18%);
              font-size: 0.98rem;
            }}

            .hero-we {{
              position: relative;
              display: inline-block;
              font-weight: 700;
              color: var(--ink);
              cursor: help;
            }}

            .hero-we-popup {{
              display: none;
              position: absolute;
              left: 0;
              bottom: calc(100% + 0.38rem);
              z-index: 40;
              padding: 0.34rem 0.5rem;
              border: 3px solid var(--outline);
              background: color-mix(in oklch, var(--screen) 95%, white 5%);
              box-shadow: 5px 5px 0 rgba(17, 24, 39, 0.16);
              font-family: "Silkscreen", monospace;
              font-size: 0.58rem;
              letter-spacing: 0.08em;
              text-transform: uppercase;
              color: var(--ink);
              white-space: nowrap;
              pointer-events: none;
            }}

            .hero-we:hover .hero-we-popup,
            .hero-we:focus-visible .hero-we-popup {{
              display: block;
            }}

            .hero-we:focus-visible {{
              outline: 3px solid color-mix(in oklch, var(--teal) 58%, white 42%);
              outline-offset: 2px;
            }}

            .hero .eyebrow {{
              margin: 0;
            }}

            .social-links {{
              display: flex;
              flex-wrap: wrap;
              justify-content: flex-end;
              gap: 0.45rem;
            }}

            .social-link {{
              display: grid;
              gap: 0.16rem;
              min-width: 10.75rem;
              padding: 0.42rem 0.62rem 0.5rem;
              border: 3px solid var(--outline);
              background: color-mix(in oklch, var(--screen) 92%, var(--gold) 8%);
              color: var(--ink);
              text-decoration: none;
              box-shadow: 4px 4px 0 rgba(17, 24, 39, 0.14);
              transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease;
            }}

            .social-link:hover,
            .social-link:focus-visible {{
              transform: translate(-1px, -1px);
              box-shadow: 6px 6px 0 rgba(17, 24, 39, 0.18);
              background: color-mix(in oklch, var(--gold) 24%, var(--screen));
            }}

            .social-link:focus-visible {{
              outline: 3px solid color-mix(in oklch, var(--teal) 58%, white 42%);
              outline-offset: 2px;
            }}

            .social-link span {{
              font-family: "Silkscreen", monospace;
              text-transform: uppercase;
              letter-spacing: 0.12em;
              font-size: 0.54rem;
              color: var(--muted);
            }}

            .social-link strong {{
              font-size: 0.9rem;
              line-height: 1.05;
            }}

            .faq-grid {{
              position: relative;
              z-index: 10;
              display: grid;
              grid-template-columns: repeat(4, minmax(0, 1fr));
              gap: 0.7rem;
              margin-bottom: 1rem;
            }}

            .faq-card {{
              position: relative;
              z-index: 0;
              overflow: visible;
              border: 3px solid var(--outline);
              background: color-mix(in oklch, var(--screen-alt) 90%, white 10%);
              padding: 0.65rem 0.75rem;
              min-height: 4.7rem;
              display: grid;
              gap: 0.25rem;
              align-content: start;
              cursor: help;
              box-shadow: 5px 5px 0 rgba(17, 24, 39, 0.1);
              transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease;
            }}

            .faq-card:hover,
            .faq-card:focus-within {{
              z-index: 30;
              transform: translate(-1px, -1px);
              box-shadow: 7px 7px 0 rgba(17, 24, 39, 0.14);
              background: color-mix(in oklch, var(--gold) 22%, var(--screen));
            }}

            .faq-card summary {{
              list-style: none;
              cursor: help;
              outline: none;
            }}

            .faq-card summary::-webkit-details-marker {{
              display: none;
            }}

            .faq-card summary::marker {{
              content: "";
            }}

            .faq-card summary strong {{
              display: block;
              font-size: 0.9rem;
              line-height: 1.15;
            }}

            .faq-card summary span {{
              display: block;
              margin-top: 0.15rem;
              color: var(--muted);
              font-size: 0.73rem;
            }}

            .faq-card summary:focus-visible {{
              outline: 3px solid color-mix(in oklch, var(--teal) 58%, white 42%);
              outline-offset: 2px;
            }}

            .faq-card[open] summary span,
            .faq-card:hover summary span,
            .faq-card:focus-within summary span {{
              color: color-mix(in oklch, var(--ink) 76%, var(--muted) 24%);
            }}

            .faq-answer {{
              display: none;
              position: absolute;
              inset: calc(100% + 0.35rem) auto auto 0;
              z-index: 50;
              width: min(320px, calc(100vw - 2.5rem));
              border: 3px solid var(--outline);
              background: color-mix(in oklch, var(--screen) 96%, white 4%);
              padding: 0.65rem 0.75rem;
              font-size: 0.84rem;
              line-height: 1.35;
              box-shadow: 7px 7px 0 rgba(17, 24, 39, 0.16);
              pointer-events: none;
            }}

            .faq-card:hover .faq-answer,
            .faq-card:focus-within .faq-answer,
            .faq-card[open] .faq-answer {{
              display: block;
            }}

            .section-stack {{
              display: grid;
              gap: 1rem;
            }}

            .playins,
            .finals,
            .region {{
              border: 4px solid var(--outline);
              background: color-mix(in oklch, var(--screen) 92%, var(--screen-alt) 8%);
              padding: 0.8rem;
              box-shadow: 6px 6px 0 rgba(17, 24, 39, 0.12);
            }}

            .playins,
            .finals {{
              display: grid;
              gap: 0.75rem;
            }}

            .finals {{
              grid-template-rows: auto 1fr;
              min-height: 100%;
            }}

            .playin-grid,
            .regions,
            .main-bracket {{
              display: grid;
              gap: 0.9rem;
            }}

            .playin-grid {{
              grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            }}

            .main-bracket {{
              grid-template-columns: minmax(0, 1fr) minmax(182px, 0.33fr) minmax(0, 1fr);
              align-items: stretch;
              gap: 0.6rem;
            }}

            .side-stack {{
              display: grid;
              grid-template-rows: repeat(2, minmax(0, 1fr));
              gap: 0.9rem;
              align-items: stretch;
              min-width: 0;
            }}

            .region {{
              display: grid;
              gap: 0.8rem;
              height: 100%;
              min-width: 0;
            }}

            .region-title {{
              display: grid;
              gap: 0.35rem;
              align-content: start;
              min-width: 0;
            }}

            .region-title > div,
            .region-title p {{
              min-width: 0;
            }}

            .region-title p {{
              max-width: 28ch;
              line-height: 1.25;
            }}

            .region-title h2,
            .finals h2 {{
              font-family: "Silkscreen", monospace;
              font-size: 1rem;
            }}

            .region-board {{
              --card-height: 238px;
              --lane-gap: 6px;
              display: grid;
              grid-template-columns: repeat(4, minmax(0, 1fr));
              gap: 0.42rem;
              align-items: stretch;
              overflow: visible;
              min-width: 0;
            }}

            .region-board--mirrored {{
              grid-template-columns: repeat(4, minmax(0, 1fr));
            }}

            .round-column {{
              position: relative;
              display: grid;
              gap: var(--round-gap, var(--lane-gap));
              padding-top: var(--round-offset, 0px);
              align-content: start;
              min-width: 0;
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

            .final-grid {{
              display: grid;
              grid-template-columns: repeat(3, minmax(0, 1fr));
              gap: 0.7rem;
              align-items: start;
            }}

            .matchup {{
              position: relative;
              border: 3px solid var(--outline);
              background: color-mix(in oklch, var(--screen-alt) 92%, white 8%);
              padding: 0.5rem;
              display: grid;
              grid-template-rows: auto minmax(0, 1fr) auto;
              gap: 0.32rem;
              align-content: start;
              overflow: visible;
              min-width: 0;
            }}

            .region-board .matchup,
            .final-grid .matchup {{
              height: var(--card-height, 248px);
            }}

            .matchup[data-round="Final4"],
            .matchup[data-round="Championship"] {{
              min-height: 100%;
            }}

            .center-stage {{
              display: flex;
              flex-direction: column;
              justify-content: space-evenly;
              gap: 0.7rem;
              height: 100%;
              padding-block: 1.2rem;
              min-height: 0;
            }}

            .center-slot {{
              display: flex;
              justify-content: center;
              min-width: 0;
            }}

            .center-slot--title {{
              margin-block: 0.15rem;
            }}

            .center-slot .matchup {{
              width: min(100%, 186px);
              height: var(--card-height);
              background: color-mix(in oklch, var(--screen) 96%, white 4%);
            }}

            .center-slot .matchup-head {{
              grid-template-columns: 1fr;
              gap: 0.16rem;
            }}

            .center-slot .matchup-head span:last-child {{
              text-align: left;
            }}

            .matchup-head {{
              display: grid;
              grid-template-columns: minmax(0, 1fr) auto;
              gap: 0.35rem 0.75rem;
              color: var(--muted);
              min-width: 0;
            }}

            .matchup-head span:last-child {{
              text-align: right;
            }}

            .team-list {{
              display: grid;
              grid-template-rows: repeat(2, minmax(0, 1fr));
              gap: 0.28rem;
              min-height: 0;
              min-width: 0;
            }}

            .team-button {{
              width: 100%;
              position: relative;
              border: 3px solid var(--outline);
              background: color-mix(in oklch, var(--screen) 88%, white 12%);
              color: var(--ink);
              font: inherit;
              text-align: left;
              padding: 0.42rem;
              display: grid;
              grid-template-rows: minmax(0, 1fr) auto;
              gap: 0.12rem;
              cursor: pointer;
              transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease, border-color 120ms ease;
              min-height: 0;
              min-width: 0;
              overflow: hidden;
              --mc-fill: 100%;
              --fill-strong: color-mix(in oklch, var(--gold) 52%, var(--screen));
              --fill-soft: color-mix(in oklch, var(--gold) 16%, var(--screen));
              --fill-edge: color-mix(in oklch, var(--gold) 78%, var(--ink) 22%);
            }}

            .team-button strong {{
              position: relative;
              z-index: 1;
              display: -webkit-box;
              font-size: 0.86rem;
              line-height: 1;
              min-height: 2em;
              overflow: hidden;
              overflow-wrap: anywhere;
              -webkit-box-orient: vertical;
              -webkit-line-clamp: 2;
            }}

            .team-button span {{
              position: relative;
              z-index: 1;
              font-size: 0.72rem;
              color: color-mix(in oklch, var(--ink) 76%, var(--muted) 24%);
            }}

            .team-button:hover {{
              transform: translate(-1px, -1px);
              box-shadow: 4px 4px 0 rgba(17, 24, 39, 0.14);
            }}

            .team-button.is-selected {{
              background: color-mix(in oklch, var(--gold) 52%, var(--screen));
              border-color: color-mix(in oklch, var(--gold) 38%, var(--outline));
              box-shadow: 0 0 0 2px color-mix(in oklch, var(--gold) 34%, transparent), 5px 5px 0 rgba(17, 24, 39, 0.18);
            }}

            .team-button.is-selected.has-mc-fill {{
              background:
                linear-gradient(
                  90deg,
                  var(--fill-strong) 0,
                  var(--fill-strong) var(--mc-fill),
                  var(--fill-soft) var(--mc-fill),
                  color-mix(in oklch, var(--screen) 88%, white 12%) var(--mc-fill),
                  color-mix(in oklch, var(--screen) 88%, white 12%) 100%
                );
            }}

            .team-button.is-selected.has-mc-fill::after {{
              content: "";
              position: absolute;
              top: 0.22rem;
              bottom: 0.22rem;
              left: clamp(0.2rem, var(--mc-fill), calc(100% - 0.2rem));
              width: 2px;
              transform: translateX(-50%);
              background: var(--fill-edge);
              opacity: 0.92;
              pointer-events: none;
            }}

            .team-button.is-underdog.is-selected {{
              --fill-strong: color-mix(in oklch, var(--coral) 34%, var(--screen));
              --fill-soft: color-mix(in oklch, var(--coral) 12%, var(--screen));
              --fill-edge: color-mix(in oklch, var(--coral) 78%, var(--ink) 22%);
              border-color: color-mix(in oklch, var(--coral) 38%, var(--outline));
              box-shadow: 0 0 0 2px color-mix(in oklch, var(--coral) 28%, transparent), 5px 5px 0 rgba(17, 24, 39, 0.18);
            }}

            .team-button.is-empty {{
              cursor: default;
              opacity: 0.7;
            }}

            .team-button:focus-visible {{
              outline: 4px solid color-mix(in oklch, var(--teal) 62%, white 38%);
              outline-offset: 2px;
              box-shadow: 0 0 0 4px color-mix(in oklch, var(--outline) 18%, transparent);
            }}

            .button-meta {{
              display: flex;
              position: relative;
              z-index: 1;
              justify-content: space-between;
              align-items: center;
              gap: 0.6rem;
              margin-top: auto;
              min-width: 0;
            }}

            .pick-pill {{
              display: inline-flex;
              flex-shrink: 0;
              align-items: center;
              justify-content: center;
              border: 2px solid color-mix(in oklch, var(--outline) 68%, transparent);
              padding: 0.08rem 0.35rem;
              font-family: "Silkscreen", monospace;
              font-size: 0.56rem;
              letter-spacing: 0.08em;
              text-transform: uppercase;
              background: color-mix(in oklch, white 58%, transparent);
              white-space: nowrap;
              min-width: 5.9ch;
            }}

            .team-button:not(.is-selected) .pick-pill {{
              opacity: 0;
            }}

            .summary-block {{
              display: grid;
              gap: 0.16rem;
              border-top: 2px solid color-mix(in oklch, var(--outline) 35%, transparent);
              padding-top: 0.24rem;
              font-size: 0.69rem;
              align-content: start;
            }}

            .summary-line {{
              display: grid;
              grid-template-columns: 5.2rem minmax(0, 1fr);
              gap: 0.28rem;
              align-items: center;
            }}

            .summary-line strong {{
              text-align: right;
              line-height: 1.1;
              font-size: 0.76rem;
              white-space: nowrap;
              overflow-wrap: normal;
            }}

            .summary-note {{
              color: var(--muted);
              line-height: 1.22;
              font-size: 0.69rem;
            }}

            .summary-label {{
              position: relative;
              appearance: none;
              border: 0;
              background: transparent;
              padding: 0;
              width: 100%;
              min-width: 0;
              color: inherit;
              text-align: left;
              cursor: help;
              font-size: 0.6rem;
              letter-spacing: 0.1em;
              line-height: 1.08;
            }}

            .summary-label::after {{
              content: attr(data-tip);
              position: absolute;
              inset: auto auto calc(100% + 0.32rem) 0;
              z-index: 14;
              width: 210px;
              display: none;
              border: 3px solid var(--outline);
              background: color-mix(in oklch, var(--screen) 96%, white 4%);
              padding: 0.5rem 0.55rem;
              font-family: "Chakra Petch", sans-serif;
              font-size: 0.77rem;
              font-weight: 500;
              line-height: 1.25;
              letter-spacing: normal;
              text-transform: none;
              box-shadow: 6px 6px 0 rgba(17, 24, 39, 0.14);
            }}

            .summary-label:hover::after,
            .summary-label:focus-visible::after {{
              display: block;
            }}

            .summary-label:focus-visible {{
              outline: 3px solid color-mix(in oklch, var(--teal) 58%, white 42%);
              outline-offset: 2px;
            }}

            .region-board .summary-block {{
              gap: 0.12rem;
              padding-top: 0.2rem;
            }}

            .region-board .summary-line {{
              grid-template-columns: minmax(0, 1fr) auto;
              gap: 0.18rem;
              align-items: start;
            }}

            .region-board .summary-line strong {{
              font-size: 0.68rem;
            }}

            .region-board .summary-label {{
              font-size: 0.5rem;
              letter-spacing: 0.08em;
            }}

            .finals {{
              height: 100%;
            }}

            @media (max-width: 1180px) {{
              .hero {{
                grid-template-columns: 1fr;
              }}

              .hero-top {{
                flex-direction: column;
                align-items: flex-start;
              }}

              .hero h1,
              .hero p,
              .hero .eyebrow,
              .hero-top {{
                grid-column: 1;
              }}

              .hero p {{
                max-width: 68ch;
              }}

              .social-links {{
                justify-content: flex-start;
              }}

              .faq-grid {{
                grid-template-columns: repeat(2, minmax(0, 1fr));
              }}

              .main-bracket {{
                grid-template-columns: 1fr;
              }}

              .region-title p {{
                max-width: 68ch;
              }}

              .center-stage {{
                grid-template-rows: none;
                padding-block: 0;
              }}

              .center-stage::before,
              .center-slot--semi::before {{
                display: none;
              }}
            }}

            @media (max-width: 900px) {{
              body {{
                padding: 0.45rem;
              }}

              .screen {{
                padding: 0.7rem;
              }}

              .hero {{
                gap: 0.35rem;
              }}

              .hero h1 {{
                max-width: 9ch;
                font-size: clamp(1.6rem, 10vw, 2.35rem);
              }}

              .hero p {{
                font-size: 1rem;
              }}

              .social-links {{
                width: 100%;
              }}

              .social-link {{
                min-width: 0;
                flex: 1 1 11rem;
              }}

              .chip {{
                width: 100%;
                font-size: 0.92rem;
              }}

              .faq-grid {{
                grid-template-columns: 1fr;
              }}

              .faq-card {{
                min-height: auto;
              }}

              .faq-answer {{
                inset: auto;
                position: static;
                width: auto;
                margin-top: 0.45rem;
                box-shadow: none;
              }}

              .region-board,
              .final-grid {{
                grid-template-columns: 1fr;
              }}

              .region-board > .round-column,
              .final-grid > .matchup {{
                grid-column: 1 !important;
              }}

              .round-column {{
                gap: 0.7rem;
                padding-top: 0;
              }}

              .region-board .round-column::before,
              .region-board .round-column::after,
              .region-board .matchup::before,
              .region-board .matchup::after {{
                display: none;
              }}

              .matchup {{
                height: auto;
                min-height: auto;
              }}

              .center-slot .matchup {{
                width: 100%;
                height: auto;
              }}

              .region-title {{
                align-items: start;
                flex-direction: column;
              }}

              .region-title p,
              .finals .region-title p,
              .playins .region-title p {{
                font-size: 0.94rem;
                max-width: 34ch;
              }}

              .matchup-head {{
                grid-template-columns: 1fr;
              }}

              .matchup-head span:last-child {{
                text-align: left;
              }}

              .summary-line {{
                grid-template-columns: 1fr;
                gap: 0.12rem;
              }}

              .summary-line strong {{
                text-align: left;
              }}

              .summary-label {{
                font-size: 0.58rem;
                letter-spacing: 0.08em;
              }}
            }}
          </style>
        </head>
        <body>
          <main class="cabinet">
            <section class="screen">
              <header class="hero">
                <div class="hero-top">
                  <p class="eyebrow">{season} bracket lab</p>
                  <nav class="social-links" aria-label="Profile links">
                    <a class="social-link" href="{github_url}" target="_blank" rel="noreferrer">
                      <span>GitHub</span>
                      <strong>{github_handle}</strong>
                    </a>
                    <a class="social-link" href="{x_url}" target="_blank" rel="noreferrer">
                      <span>X</span>
                      <strong>{x_handle}</strong>
                    </a>
                  </nav>
                </div>
                <h1>Build a smarter bracket by playing the odds.</h1>
                <p><span class="hero-we" tabindex="0">We<span class="hero-we-popup">Me and Codex</span></span> ran the 2026 tournament 100,000 times and logged the results. Click teams to advance and build your bracket. Every card shows the selected team's Elo win probability, the simulated win rate when that matchup happened, and how often that exact matchup appeared in our simulations.</p>
              </header>

              <section class="section-stack" id="app"></section>
            </section>
          </main>

          <script>
            const APP_DATA = {json.dumps(payload)};
            const app = document.getElementById("app");
            const teamLookup = Object.fromEntries(APP_DATA.teams.map((team) => [team.team_id, team]));
            const regionLookup = Object.fromEntries(APP_DATA.regions.map((region) => [region.name, region]));
            const gameLookup = APP_DATA.games;
            const selections = Object.create(null);
            const matchupLookup = new Map(
              APP_DATA.matchups.map((row) => [
                [row.round, row.team_a_id_canon, row.team_b_id_canon].join("|"),
                row,
              ]),
            );

            function roundLabel(roundName) {{
              return APP_DATA.roundLabels[roundName] ?? roundName;
            }}

            function resolveSource(source) {{
              if (!source) {{
                return null;
              }}
              if (source.type === "team") {{
                return teamLookup[source.teamId] ?? null;
              }}
              if (source.type === "game") {{
                const winnerId = selections[source.gameId];
                return winnerId ? teamLookup[winnerId] ?? null : null;
              }}
              return null;
            }}

            function entrantsFor(game) {{
              return [resolveSource(game.slotA), resolveSource(game.slotB)];
            }}

            function preferredWinner(teamA, teamB) {{
              if (teamA.elo !== teamB.elo) {{
                return teamA.elo > teamB.elo ? teamA.team_id : teamB.team_id;
              }}
              if (teamA.seed !== teamB.seed) {{
                return teamA.seed < teamB.seed ? teamA.team_id : teamB.team_id;
              }}
              return teamA.name.localeCompare(teamB.name) <= 0 ? teamA.team_id : teamB.team_id;
            }}

            function normalizeKey(roundName, teamA, teamB) {{
              const ordered = [teamA.team_id, teamB.team_id].sort();
              return [roundName, ordered[0], ordered[1]].join("|");
            }}

            function ensureSelections() {{
              APP_DATA.gameOrder.forEach((gameId) => {{
                const game = gameLookup[gameId];
                const [teamA, teamB] = entrantsFor(game);
                const validIds = [teamA, teamB].filter(Boolean).map((team) => team.team_id);
                if (!validIds.includes(selections[gameId])) {{
                  delete selections[gameId];
                }}
                if (!selections[gameId] && teamA && teamB) {{
                  selections[gameId] = preferredWinner(teamA, teamB);
                }}
              }});
            }}

            function rawEloWinPct(teamA, teamB) {{
              return 100 / (1 + Math.pow(10, (teamB.elo - teamA.elo) / 400));
            }}

            function formatPct(value) {{
              return `${{Number(value).toFixed(1)}}%`;
            }}

            function formatCount(value) {{
              return Number(value).toLocaleString();
            }}

            function summaryLabelMarkup(label, tip) {{
              return `
                <button class="summary-label" type="button" data-tip="${{tip}}">
                  ${{label}}
                </button>
              `;
            }}

            function matchupRowForGame(game, teamA, teamB) {{
              if (!teamA || !teamB || game.round === "FirstFour") {{
                return null;
              }}
              return matchupLookup.get(normalizeKey(game.round, teamA, teamB)) ?? null;
            }}

            function matchupWinPct(matchup, teamId) {{
              if (!matchup) {{
                return null;
              }}
              return matchup.team_a_id_canon === teamId
                ? matchup.team_a_win_pct_when_met
                : matchup.team_b_win_pct_when_met;
            }}

            function teamButtonMarkup(team, selectedId, gameId, disabled, mcFillPct = null) {{
              if (!team) {{
                return `
                  <button class="team-button is-empty" type="button" disabled>
                    <strong>Await prior result</strong>
                    <span>pick an earlier game first</span>
                  </button>
                `;
              }}
              const selected = selectedId === team.team_id;
              const otherEntrants = entrantsFor(gameLookup[gameId]).filter(Boolean);
              const favoriteId = otherEntrants.length === 2 ? preferredWinner(otherEntrants[0], otherEntrants[1]) : team.team_id;
              const upsetClass = favoriteId !== team.team_id ? " is-underdog" : "";
              const clampedFill = mcFillPct === null ? null : Math.max(0, Math.min(Number(mcFillPct), 100));
              const fillClass = selected && clampedFill !== null ? " has-mc-fill" : "";
              const fillStyle = selected && clampedFill !== null ? `style="--mc-fill:${{clampedFill.toFixed(1)}}%;"` : "";
              return `
                <button
                  class="team-button${{selected ? " is-selected" : ""}}${{upsetClass}}${{fillClass}}"
                  type="button"
                  data-game-id="${{gameId}}"
                  data-team-id="${{team.team_id}}"
                  ${{fillStyle}}
                  ${{disabled ? "disabled" : ""}}
                >
                  <strong>${{team.name}}</strong>
                  <div class="button-meta">
                    <span>Elo ${{team.elo.toFixed(1)}}</span>
                    <span class="pick-pill">${{selected ? "pick" : "ready"}}</span>
                  </div>
                </button>
              `;
            }}

            function summaryMarkup(game, teamA, teamB, selectedId) {{
              if (!teamA || !teamB) {{
                return `
                  <div class="summary-block">
                    <p class="summary-note">Pick the earlier game first to fill this matchup.</p>
                  </div>
                `;
              }}

              const selectedTeam = selectedId === teamB.team_id ? teamB : teamA;
              const rawA = rawEloWinPct(teamA, teamB);
              const rawSelected = selectedTeam.team_id === teamA.team_id ? rawA : 100 - rawA;
              const rawLabel = summaryLabelMarkup(
                "Raw Elo",
                "This is the implied win probability using only each team's Elo."
              );
              const monteLabel = summaryLabelMarkup(
                "Monte Carlo",
                `This is how the matchup went in our ${{formatCount(APP_DATA.simulationCount)}} simulated tournaments.`
              );
              const occurrenceLabel = summaryLabelMarkup(
                "Occurrence",
                `This is how many times this exact matchup happened in our ${{formatCount(APP_DATA.simulationCount)}} simulated tournaments.`
              );

              if (game.round === "FirstFour") {{
                return `
                  <div class="summary-block">
                    <div class="summary-line">
                      ${{rawLabel}}
                      <strong>${{formatPct(rawSelected)}}</strong>
                    </div>
                    <div class="summary-line">
                      ${{monteLabel}}
                      <strong>N/A</strong>
                    </div>
                    <div class="summary-line">
                      ${{occurrenceLabel}}
                      <strong>N/A</strong>
                    </div>
                    <p class="summary-note">The saved tournament file starts with the main 64-team bracket, so First Four meetings are not tracked here.</p>
                  </div>
                `;
              }}

              const matchup = matchupLookup.get(normalizeKey(game.round, teamA, teamB));
              if (!matchup) {{
                return `
                  <div class="summary-block">
                    <div class="summary-line">
                      ${{rawLabel}}
                      <strong>${{formatPct(rawSelected)}}</strong>
                    </div>
                    <div class="summary-line">
                      ${{monteLabel}}
                      <strong>0.0%</strong>
                    </div>
                    <div class="summary-line">
                      ${{occurrenceLabel}}
                      <strong>0.0%</strong>
                    </div>
                  </div>
                `;
              }}

              const selectedKey = matchup.team_a_id_canon === selectedTeam.team_id ? "team_a" : "team_b";
              const montePct = matchup[`${{selectedKey}}_win_pct_when_met`];
              return `
                <div class="summary-block">
                  <div class="summary-line">
                    ${{rawLabel}}
                    <strong>${{formatPct(rawSelected)}}</strong>
                  </div>
                  <div class="summary-line">
                    ${{monteLabel}}
                    <strong>${{formatPct(montePct)}}</strong>
                  </div>
                  <div class="summary-line">
                    ${{occurrenceLabel}}
                    <strong>${{formatPct(matchup.matchup_pct)}}</strong>
                  </div>
                </div>
              `;
            }}

            function renderMatchup(game) {{
              const [teamA, teamB] = entrantsFor(game);
              const selectedId = selections[game.id] ?? "";
              const matchup = matchupRowForGame(game, teamA, teamB);
              const teamAFillPct = matchupWinPct(matchup, teamA?.team_id);
              const teamBFillPct = matchupWinPct(matchup, teamB?.team_id);
              const title = game.label ?? "";
              return `
                <article class="matchup" data-round="${{game.round}}">
                  <div class="matchup-head">
                    <span>${{roundLabel(game.round)}}</span>
                    ${{title ? `<span>${{title}}</span>` : ""}}
                  </div>
                  <div class="team-list">
                    ${{teamButtonMarkup(teamA, selectedId, game.id, !teamA, teamAFillPct)}}
                    ${{teamButtonMarkup(teamB, selectedId, game.id, !teamB, teamBFillPct)}}
                  </div>
                  ${{summaryMarkup(game, teamA, teamB, selectedId)}}
                </article>
              `;
            }}

            function renderFaqs() {{
              const topTeam = APP_DATA.siteInsights.mostLikelyChampion;
              const topPct = formatPct(APP_DATA.siteInsights.mostLikelyChampionPct);
              const longshot = APP_DATA.siteInsights.leastLikelyChampion;
              const longshotCount = APP_DATA.siteInsights.leastLikelyChampionCount;
              const longshotText = longshotCount === 1 ? "won once" : `won ${{formatCount(longshotCount)}} times`;
              const cards = [
                {{
                  question: "What exactly is Elo?",
                  short: "Team strength rating. Tap for more detail.",
                  answer:
                    "Elo ratings measure team strength based on past performance. Originally made by Arpad Elo for chess, a higher Elo means a stronger team. I use the Elo difference between teams to calculate each matchup's win probability."
                }},
                {{
                  question: "How do I make my picks?",
                  short: "Choose teams to advance. Tap for more detail.",
                  answer:
                    "Just click the team you think will win each game. Explore how probabilities change by creating different scenarios. You may want to compare simulated win percentage to public opinion to find sneaky underdogs."
                }},
                {{
                  question: "What's a Monte Carlo simulation?",
                  short: "Simulating 100,000 tournaments. Tap for more detail.",
                  answer:
                    `Monte Carlo simulations replay the entire tournament thousands of times, randomly—but realistically—based on each team's chance to win. It's widely used in fields like finance, risk management, and sports to capture possible outcomes beyond a single scenario. This site draws from ${{formatCount(APP_DATA.simulationCount)}} simulated tournaments.`
                }},
                {{
                  question: "Who will win the whole thing?",
                  short: "We don't know. Tap for more detail.",
                  answer:
                    `No crystal balls here—but according to this model, ${{topTeam}} took home the title ${{topPct}} of the time across ${{formatCount(APP_DATA.simulationCount)}} simulations. Even ${{longshot}} ${{longshotText}}. Anything can happen.`
                }},
              ];

              return `
                <section class="faq-grid">
                  ${{cards.map((card) => `
                    <details class="faq-card">
                      <summary>
                        <strong>${{card.question}}</strong>
                        <span>${{card.short}}</span>
                      </summary>
                      <div class="faq-answer">${{card.answer}}</div>
                    </details>
                  `).join("")}}
                </section>
              `;
            }}

            function renderPlayIns() {{
              if (!APP_DATA.playInIds.length) {{
                return "";
              }}
              return `
                <section class="playins">
                  <div class="region-title">
                    <div>
                      <span class="eyebrow">Play-in games</span>
                      <h2>First Four</h2>
                    </div>
                    <p>Pick the play-in winners here. Those winners feed straight into the main bracket.</p>
                  </div>
                  <div class="playin-grid">
                    ${{APP_DATA.playInIds.map((gameId) => renderMatchup(gameLookup[gameId])).join("")}}
                  </div>
                </section>
              `;
            }}

            function renderRegions() {{
              return "";
            }}

            function renderRegionPanel(regionName, mirrored = false) {{
              const region = regionLookup[regionName];
              const roundOrder = mirrored
                ? ["Elite8", "Sweet16", "R32", "R64"]
                : ["R64", "R32", "Sweet16", "Elite8"];
              const regionColumns = roundOrder
                .map((roundName) => `
                  <div class="round-column" data-round="${{roundName}}">
                    ${{region.games[roundName].map((gameId) => renderMatchup(gameLookup[gameId])).join("")}}
                  </div>
                `)
                .join("");
              return `
                <section class="region ${{mirrored ? "region--mirrored" : "region--standard"}}">
                  <div class="region-title">
                    <div>
                      <span>${{region.name}} sector</span>
                      <h2>${{region.name}}</h2>
                    </div>
                    <p>Click teams to explore possibilities.</p>
                  </div>
                  <div class="region-board ${{mirrored ? "region-board--mirrored" : "region-board--standard"}}">
                    ${{regionColumns}}
                  </div>
                </section>
              `;
            }}

            function renderCenterStage() {{
              return `
                <section class="finals">
                  <div class="region-title">
                    <div>
                      <span class="eyebrow">Final rounds</span>
                      <h2>Final Four + Title</h2>
                    </div>
                    <p>These games fill in once your regional winners are set.</p>
                  </div>
                  <div class="center-stage">
                    <div class="center-slot center-slot--semi">
                      ${{renderMatchup(gameLookup[APP_DATA.finalFourIds[0]])}}
                    </div>
                    <div class="center-slot center-slot--title">
                      ${{renderMatchup(gameLookup[APP_DATA.championshipId])}}
                    </div>
                    <div class="center-slot center-slot--semi">
                      ${{renderMatchup(gameLookup[APP_DATA.finalFourIds[1]])}}
                    </div>
                  </div>
                </section>
              `;
            }}

            function renderBracketStage() {{
              const pairings = APP_DATA.finalFourPairings ?? [["East", "South"], ["Midwest", "West"]];
              const leftRegionNames = pairings.map((pairing) => pairing[0]);
              const rightRegionNames = pairings.map((pairing) => pairing[1]);
              return `
                <section class="main-bracket">
                  <div class="side-stack side-stack--left">
                    ${{leftRegionNames.map((regionName) => renderRegionPanel(regionName, false)).join("")}}
                  </div>
                  ${{renderCenterStage()}}
                  <div class="side-stack side-stack--right">
                    ${{rightRegionNames.map((regionName) => renderRegionPanel(regionName, true)).join("")}}
                  </div>
                </section>
              `;
            }}

            function render() {{
              ensureSelections();
              app.innerHTML = [renderFaqs(), renderPlayIns(), renderBracketStage()].join("");
              app.querySelectorAll("[data-game-id][data-team-id]").forEach((button) => {{
                button.addEventListener("click", () => {{
                  selections[button.dataset.gameId] = button.dataset.teamId;
                  render();
                }});
              }});
            }}

            render();
          </script>
        </body>
        </html>
        """
    ).strip()

    destination.write_text(document, encoding="utf-8")
    return destination
