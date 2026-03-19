from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape
from pathlib import Path
from textwrap import dedent

import pandas as pd

from .constants import DEFAULT_SEASON
from .paths import output_dir, processed_dir
from .pixel_icon import favicon_head_tags


REGION_CLASSES = {
    "East": "east",
    "West": "west",
    "South": "south",
    "Midwest": "midwest",
}


@dataclass(frozen=True)
class TeamMetrics:
    team_id: str
    name: str
    seed: int
    rating: float
    r64_pct: float
    r32_pct: float
    sweet16_pct: float
    elite8_pct: float
    final4_pct: float
    championship_pct: float
    champion_pct: float


def _format_pct(value: float) -> str:
    return f"{value:.1f}%"


def _load_inputs(
    season: int,
    processed_root: Path,
    output_root: Path,
) -> tuple[dict[str, TeamMetrics], pd.DataFrame, pd.DataFrame, dict[str, object], int, str]:
    results = pd.read_csv(output_root / "monte_carlo_tourney_results.csv")
    ratings = pd.read_csv(output_root / "combined_ratings.csv")
    round64 = pd.read_csv(processed_root / "bracket_round64.csv")
    first_four_path = processed_root / "first_four.csv"
    first_four = pd.read_csv(first_four_path) if first_four_path.exists() else pd.DataFrame()
    metadata_path = processed_root / "bracket_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}

    simulation_count = int(results["simulation_count"].dropna().iloc[0])
    merged = results.merge(
        ratings[["team_id_canon", "Team", "blended_elo_scale", "efficiency_source"]],
        on=["team_id_canon", "Team"],
        how="left",
    )

    seed_lookup: dict[str, int] = {}
    for row in round64.to_dict("records"):
        if pd.notna(row.get("team_top")):
            seed_lookup[str(row["team_top"])] = int(row["seed_top"])
        if pd.notna(row.get("team_bottom")):
            seed_lookup[str(row["team_bottom"])] = int(row["seed_bottom"])

    if not first_four.empty:
        for row in first_four.to_dict("records"):
            seed_lookup[str(row["team_a_id_canon"])] = int(row["seed"])
            seed_lookup[str(row["team_b_id_canon"])] = int(row["seed"])

    metrics: dict[str, TeamMetrics] = {}
    for row in merged.to_dict("records"):
        team_id = str(row["team_id_canon"])
        metrics[team_id] = TeamMetrics(
            team_id=team_id,
            name=str(row["Team"]),
            seed=seed_lookup.get(team_id, 0),
            rating=float(row["blended_elo_scale"]),
            r64_pct=(float(row["R64"]) / simulation_count) * 100.0,
            r32_pct=(float(row["R32"]) / simulation_count) * 100.0,
            sweet16_pct=(float(row["Sweet16"]) / simulation_count) * 100.0,
            elite8_pct=(float(row["Elite8"]) / simulation_count) * 100.0,
            final4_pct=(float(row["Final4"]) / simulation_count) * 100.0,
            championship_pct=(float(row["Championship"]) / simulation_count) * 100.0,
            champion_pct=(float(row["Champion"]) / simulation_count) * 100.0,
        )

    efficiency_source = str(merged["efficiency_source"].dropna().iloc[0]) if "efficiency_source" in merged else "unknown"
    metadata.setdefault("season", season)
    return metrics, round64, first_four, metadata, simulation_count, efficiency_source


def _build_play_in_lookup(first_four: pd.DataFrame) -> dict[str, list[str]]:
    lookup: dict[str, list[str]] = {}
    if first_four.empty:
        return lookup
    for row in first_four.to_dict("records"):
        lookup[str(row["group_id"])] = [str(row["team_a_id_canon"]), str(row["team_b_id_canon"])]
    return lookup


def _team_ids_from_matchup(row: dict[str, object], play_in_lookup: dict[str, list[str]]) -> list[str]:
    team_ids: list[str] = []
    if pd.notna(row.get("team_top")):
        team_ids.append(str(row["team_top"]))
    elif pd.notna(row.get("play_in_group_top")):
        team_ids.extend(play_in_lookup[str(row["play_in_group_top"])])
    if pd.notna(row.get("team_bottom")):
        team_ids.append(str(row["team_bottom"]))
    elif pd.notna(row.get("play_in_group_bottom")):
        team_ids.extend(play_in_lookup[str(row["play_in_group_bottom"])])
    return team_ids


def _select_best(team_ids: list[str], metrics: dict[str, TeamMetrics], attribute: str) -> TeamMetrics:
    return max(
        (metrics[team_id] for team_id in team_ids),
        key=lambda item: (getattr(item, attribute), item.champion_pct, item.rating),
    )


def _slot_payload(
    team_id: str | None,
    play_in_group: str | None,
    seed: int,
    metrics: dict[str, TeamMetrics],
    play_in_lookup: dict[str, list[str]],
) -> dict[str, object]:
    if team_id:
        entry = metrics[team_id]
        return {
            "seed": seed,
            "label": entry.name,
            "open_win_pct": entry.r32_pct,
            "title_pct": entry.champion_pct,
            "tagline": "",
            "rating": int(round(entry.rating)),
            "is_play_in": False,
        }

    group_members = [metrics[team_key] for team_key in play_in_lookup[play_in_group]]
    combined_open_pct = sum(item.r32_pct for item in group_members)
    split = " / ".join(f"{item.name} {_format_pct(item.r64_pct)}" for item in group_members)
    power = int(round(sum(item.rating for item in group_members) / len(group_members)))
    return {
        "seed": seed,
        "label": " / ".join(item.name for item in group_members),
        "open_win_pct": combined_open_pct,
        "title_pct": max(item.champion_pct for item in group_members),
        "tagline": f"play-in split {split}",
        "rating": power,
        "is_play_in": True,
    }


def _render_opening_card(card: dict[str, object], accent_class: str) -> str:
    top_slot = card["top"]
    bottom_slot = card["bottom"]
    favorite_label = "top" if float(top_slot["open_win_pct"]) >= float(bottom_slot["open_win_pct"]) else "bottom"
    favorite_slot = top_slot if favorite_label == "top" else bottom_slot
    top_class = " duel-row--favorite" if favorite_label == "top" else ""
    bottom_class = " duel-row--favorite" if favorite_label == "bottom" else ""
    note = card.get("note")
    note_markup = f'<p class="slot__note">{escape(str(note))}</p>' if note else ""
    return dedent(
        f"""
        <article class="slot slot--opening slot--{accent_class}" style="--column: 1; --row-start: {card['row_start']}; --row-span: 1;">
          <div class="slot__eyebrow">Round 64</div>
          <div class="duel-row{top_class}">
            <span class="seed-chip">{top_slot['seed']}</span>
            <span class="duel-row__name">{escape(str(top_slot['label']))}</span>
            <span class="duel-row__stat">{_format_pct(float(top_slot['open_win_pct']))}</span>
          </div>
          <div class="duel-row{bottom_class}">
            <span class="seed-chip">{bottom_slot['seed']}</span>
            <span class="duel-row__name">{escape(str(bottom_slot['label']))}</span>
            <span class="duel-row__stat">{_format_pct(float(bottom_slot['open_win_pct']))}</span>
          </div>
          <p class="slot__subtext">fav: {escape(str(favorite_slot['label']))} · title {_format_pct(float(favorite_slot['title_pct']))}</p>
          {note_markup}
        </article>
        """
    ).strip()


def _render_projection_card(card: dict[str, object], accent_class: str) -> str:
    return dedent(
        f"""
        <article class="slot slot--projection slot--{accent_class}" style="--column: {card['column']}; --row-start: {card['row_start']}; --row-span: {card['row_span']};">
          <div class="slot__eyebrow">{escape(str(card['eyebrow']))}</div>
          <div class="slot__headline">
            <span class="seed-chip">{card['seed']}</span>
            <h3>{escape(str(card['name']))}</h3>
          </div>
          <p class="slot__metric">{_format_pct(float(card['metric']))} {escape(str(card['metric_label']))}</p>
          <p class="slot__subtext">title {_format_pct(float(card['champion_pct']))} · power {int(round(float(card['rating'])))} </p>
        </article>
        """
    ).strip()


def _render_region_panel(
    region: str,
    region_rows: pd.DataFrame,
    metrics: dict[str, TeamMetrics],
    play_in_lookup: dict[str, list[str]],
) -> tuple[str, TeamMetrics]:
    accent_class = REGION_CLASSES[region]
    rows = region_rows.sort_values("matchup_order").to_dict("records")

    opening_cards: list[str] = []
    matchup_team_ids: list[list[str]] = []
    for index, row in enumerate(rows, start=1):
        top_team_id = str(row["team_top"]) if pd.notna(row.get("team_top")) else None
        bottom_team_id = str(row["team_bottom"]) if pd.notna(row.get("team_bottom")) else None
        play_in_top = str(row["play_in_group_top"]) if pd.notna(row.get("play_in_group_top")) else None
        play_in_bottom = str(row["play_in_group_bottom"]) if pd.notna(row.get("play_in_group_bottom")) else None
        top_slot = _slot_payload(top_team_id, play_in_top, int(row["seed_top"]), metrics, play_in_lookup)
        bottom_slot = _slot_payload(bottom_team_id, play_in_bottom, int(row["seed_bottom"]), metrics, play_in_lookup)
        note_parts = [str(part) for part in (top_slot["tagline"], bottom_slot["tagline"]) if part]
        opening_cards.append(
            _render_opening_card(
                {
                    "row_start": index,
                    "top": top_slot,
                    "bottom": bottom_slot,
                    "note": " · ".join(note_parts),
                },
                accent_class,
            )
        )
        matchup_team_ids.append(_team_ids_from_matchup(row, play_in_lookup))

    projection_cards: list[str] = []

    for card_index, matchup_index in enumerate(range(0, 8, 2), start=1):
        best = _select_best(matchup_team_ids[matchup_index] + matchup_team_ids[matchup_index + 1], metrics, "sweet16_pct")
        projection_cards.append(
            _render_projection_card(
                {
                    "column": 2,
                    "row_start": (card_index * 2) - 1,
                    "row_span": 2,
                    "eyebrow": "Pod favorite",
                    "seed": best.seed,
                    "name": best.name,
                    "metric": best.sweet16_pct,
                    "metric_label": "to reach Sweet 16",
                    "champion_pct": best.champion_pct,
                    "rating": best.rating,
                },
                accent_class,
            )
        )

    for card_index, matchup_index in enumerate(range(0, 8, 4), start=1):
        best = _select_best(
            matchup_team_ids[matchup_index]
            + matchup_team_ids[matchup_index + 1]
            + matchup_team_ids[matchup_index + 2]
            + matchup_team_ids[matchup_index + 3],
            metrics,
            "elite8_pct",
        )
        projection_cards.append(
            _render_projection_card(
                {
                    "column": 3,
                    "row_start": (card_index * 4) - 3,
                    "row_span": 4,
                    "eyebrow": "Sweet 16 lane",
                    "seed": best.seed,
                    "name": best.name,
                    "metric": best.elite8_pct,
                    "metric_label": "to reach Elite 8",
                    "champion_pct": best.champion_pct,
                    "rating": best.rating,
                },
                accent_class,
            )
        )

    region_boss = _select_best([team_id for matchup in matchup_team_ids for team_id in matchup], metrics, "final4_pct")
    projection_cards.append(
        _render_projection_card(
            {
                "column": 4,
                "row_start": 1,
                "row_span": 8,
                "eyebrow": "Region boss",
                "seed": region_boss.seed,
                "name": region_boss.name,
                "metric": region_boss.final4_pct,
                "metric_label": "to make the Final Four",
                "champion_pct": region_boss.champion_pct,
                "rating": region_boss.rating,
            },
            accent_class,
        )
    )

    panel_markup = dedent(
        f"""
        <section class="region region--{accent_class}">
          <header class="region__header">
            <p class="region__kicker">{escape(region)} sector</p>
            <div class="region__headline">
              <h2>{escape(region_boss.name)}</h2>
              <div class="region__badge">{_format_pct(region_boss.final4_pct)} to clear the region</div>
            </div>
          </header>
          <div class="region__legend">
            <span>Openers</span>
            <span>Sweet 16</span>
            <span>Elite 8</span>
            <span>Final Four</span>
          </div>
          <div class="region__grid">
            {"".join(opening_cards)}
            {"".join(projection_cards)}
          </div>
        </section>
        """
    ).strip()
    return panel_markup, region_boss


def _render_leaderboard(cards: list[TeamMetrics]) -> str:
    rows = []
    for index, item in enumerate(cards, start=1):
        rows.append(
            dedent(
                f"""
                <li class="leaderboard__row">
                  <span class="leaderboard__rank">{index:02d}</span>
                  <span class="leaderboard__name">{escape(item.name)}</span>
                  <span class="leaderboard__stat">{_format_pct(item.champion_pct)}</span>
                </li>
                """
            ).strip()
        )
    return "".join(rows)


def _render_final_four_pairings(pairings: list[list[str]], bosses: dict[str, TeamMetrics]) -> str:
    cards = []
    for left_region, right_region in pairings:
        left = bosses[left_region]
        right = bosses[right_region]
        favorite = left if left.championship_pct >= right.championship_pct else right
        cards.append(
            dedent(
                f"""
                <article class="showdown">
                  <div class="showdown__vs">
                    <span>{escape(left_region)}</span>
                    <span class="showdown__divider">vs</span>
                    <span>{escape(right_region)}</span>
                  </div>
                  <div class="showdown__teams">
                    <div>
                      <strong>{escape(left.name)}</strong>
                      <span>{_format_pct(left.championship_pct)} to reach title game</span>
                    </div>
                    <div>
                      <strong>{escape(right.name)}</strong>
                      <span>{_format_pct(right.championship_pct)} to reach title game</span>
                    </div>
                  </div>
                  <p class="showdown__favorite">lane favorite: {escape(favorite.name)}</p>
                </article>
                """
            ).strip()
        )
    return "".join(cards)


def _build_document(
    season: int,
    simulation_count: int,
    efficiency_source: str,
    metadata: dict[str, object],
    left_panels: str,
    right_panels: str,
    bosses: dict[str, TeamMetrics],
    leaderboard: list[TeamMetrics],
    favicon_tags: str,
) -> str:
    pairings = metadata.get("final_four_pairings", [["East", "South"], ["Midwest", "West"]])
    host_city = escape(str(metadata.get("host_city", "Indianapolis")))
    top_seed = leaderboard[0]
    season_label = escape(str(season))
    efficiency_note = "Torvik fallback" if efficiency_source.lower() == "torvik" else efficiency_source.title()
    return dedent(
        f"""
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>{season_label} Monte Carlo Arcade Bracket</title>
          {favicon_tags}
          <link rel="preconnect" href="https://fonts.googleapis.com">
          <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
          <link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@400;500;600;700&family=Silkscreen:wght@400;700&display=swap" rel="stylesheet">
          <style>
            :root {{
              --bg: oklch(18% 0.03 233);
              --bg-deep: oklch(13% 0.02 236);
              --screen: oklch(93% 0.03 85);
              --screen-shadow: oklch(81% 0.05 85);
              --ink: oklch(27% 0.05 241);
              --muted: oklch(48% 0.04 240);
              --gold: oklch(80% 0.16 92);
              --gold-deep: oklch(64% 0.14 86);
              --east: oklch(69% 0.18 28);
              --west: oklch(74% 0.16 185);
              --south: oklch(82% 0.16 103);
              --midwest: oklch(70% 0.14 250);
              --cabinet: oklch(29% 0.05 28);
              --cabinet-edge: oklch(39% 0.08 34);
              --outline: oklch(23% 0.04 244);
              --shadow: rgba(17, 24, 39, 0.26);
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
                radial-gradient(circle at top, color-mix(in oklch, var(--gold) 18%, transparent), transparent 36%),
                linear-gradient(180deg, color-mix(in oklch, var(--cabinet) 82%, var(--bg)) 0%, var(--bg-deep) 100%);
              padding: clamp(1rem, 2vw, 2rem);
            }}

            body::before {{
              content: "";
              position: fixed;
              inset: 0;
              background:
                linear-gradient(135deg, transparent 0 45%, color-mix(in oklch, var(--gold) 12%, transparent) 45% 55%, transparent 55% 100%),
                radial-gradient(circle at 20% 10%, color-mix(in oklch, var(--east) 20%, transparent), transparent 24%),
                radial-gradient(circle at 80% 0%, color-mix(in oklch, var(--west) 20%, transparent), transparent 20%);
              opacity: 0.35;
              pointer-events: none;
            }}

            .cabinet {{
              position: relative;
              max-width: 1800px;
              margin: 0 auto;
              border: 6px solid var(--cabinet-edge);
              background: linear-gradient(180deg, color-mix(in oklch, var(--cabinet) 76%, var(--gold) 24%), var(--cabinet));
              padding: clamp(1rem, 2vw, 1.5rem);
              box-shadow:
                0 22px 50px var(--shadow),
                0 0 0 6px color-mix(in oklch, var(--cabinet-edge) 70%, var(--outline) 30%);
            }}

            .screen {{
              position: relative;
              overflow: hidden;
              background: linear-gradient(180deg, color-mix(in oklch, var(--screen) 85%, var(--gold) 15%), var(--screen));
              border: 5px solid var(--outline);
              padding: clamp(0.8rem, 1.4vw, 1.35rem);
              box-shadow:
                inset 0 0 0 3px color-mix(in oklch, var(--screen-shadow) 70%, var(--outline) 30%),
                inset 0 0 60px color-mix(in oklch, var(--gold) 10%, transparent);
            }}

            .screen::before {{
              content: "";
              position: absolute;
              inset: 0;
              background:
                repeating-linear-gradient(
                  180deg,
                  rgba(255, 255, 255, 0.0) 0 6px,
                  rgba(22, 34, 62, 0.085) 6px 8px
                );
              mix-blend-mode: multiply;
              pointer-events: none;
            }}

            .masthead {{
              position: relative;
              display: grid;
              grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr);
              gap: 1rem;
              align-items: end;
              margin-bottom: 1.5rem;
            }}

            .title-block {{
              display: grid;
              gap: 0.6rem;
            }}

            .title-block__eyebrow,
            .region__kicker,
            .slot__eyebrow,
            .boss-board__eyebrow {{
              font-family: "Silkscreen", monospace;
              font-size: 0.72rem;
              letter-spacing: 0.12em;
              text-transform: uppercase;
            }}

            .title-block__eyebrow {{
              color: var(--muted);
            }}

            h1,
            h2,
            h3,
            p {{
              margin: 0;
            }}

            h1 {{
              font-family: "Silkscreen", monospace;
              font-size: clamp(1.8rem, 3.6vw, 4rem);
              line-height: 0.95;
              max-width: 12ch;
              text-transform: uppercase;
              text-shadow: 4px 4px 0 color-mix(in oklch, var(--gold) 30%, transparent);
            }}

            .title-block__subhead {{
              max-width: 58ch;
              color: color-mix(in oklch, var(--ink) 76%, var(--muted) 24%);
              font-size: clamp(0.95rem, 1.2vw, 1.15rem);
            }}

            .marquee {{
              display: grid;
              gap: 0.55rem;
              justify-items: stretch;
            }}

            .marquee__board {{
              display: grid;
              gap: 0.55rem;
              border: 4px solid var(--outline);
              padding: 0.9rem;
              background: color-mix(in oklch, var(--gold) 20%, var(--screen));
              box-shadow: 6px 6px 0 color-mix(in oklch, var(--gold-deep) 40%, transparent);
            }}

            .marquee__line {{
              display: flex;
              justify-content: space-between;
              gap: 0.75rem;
              font-weight: 600;
              color: color-mix(in oklch, var(--ink) 88%, var(--muted) 12%);
            }}

            .marquee__line span:last-child {{
              color: color-mix(in oklch, var(--gold-deep) 72%, var(--ink) 28%);
            }}

            .arena {{
              display: grid;
              grid-template-columns: minmax(0, 1.42fr) minmax(220px, 0.52fr) minmax(0, 1.42fr);
              gap: 0.65rem;
              align-items: stretch;
            }}

            .rail {{
              display: grid;
              gap: 1rem;
            }}

            .region {{
              display: grid;
              gap: 0.8rem;
              border: 4px solid var(--outline);
              padding: 0.75rem;
              background: color-mix(in oklch, var(--screen) 88%, transparent);
              box-shadow: 7px 7px 0 var(--shadow);
            }}

            .region--east {{
              background: color-mix(in oklch, var(--east) 10%, var(--screen));
            }}

            .region--west {{
              background: color-mix(in oklch, var(--west) 10%, var(--screen));
            }}

            .region--south {{
              background: color-mix(in oklch, var(--south) 14%, var(--screen));
            }}

            .region--midwest {{
              background: color-mix(in oklch, var(--midwest) 10%, var(--screen));
            }}

            .region__headline {{
              display: flex;
              flex-wrap: wrap;
              justify-content: space-between;
              gap: 0.75rem;
              align-items: center;
            }}

            .region h2 {{
              font-size: clamp(1.25rem, 1.6vw, 1.9rem);
              text-transform: uppercase;
            }}

            .region__badge {{
              border: 3px solid var(--outline);
              background: color-mix(in oklch, var(--gold) 16%, var(--screen));
              padding: 0.35rem 0.55rem;
              font-family: "Silkscreen", monospace;
              font-size: 0.66rem;
              text-transform: uppercase;
            }}

            .region__legend {{
              display: grid;
              grid-template-columns: repeat(4, minmax(0, 1fr));
              gap: 0.5rem;
              font-size: 0.72rem;
              text-transform: uppercase;
              color: var(--muted);
            }}

            .region__grid {{
              display: grid;
              grid-template-columns: minmax(150px, 1.48fr) minmax(104px, 1fr) minmax(104px, 1fr) minmax(104px, 1fr);
              grid-template-rows: repeat(8, minmax(76px, auto));
              gap: 0.5rem;
              min-height: 670px;
            }}

            .slot {{
              position: relative;
              display: grid;
              gap: 0.35rem;
              border: 3px solid var(--outline);
              background: color-mix(in oklch, var(--screen) 90%, white 10%);
              padding: 0.55rem;
              box-shadow: 5px 5px 0 var(--shadow);
              grid-column: var(--column);
              grid-row: var(--row-start) / span var(--row-span);
              align-self: center;
              min-width: 0;
            }}

            .slot::after {{
              content: "";
              position: absolute;
              inset: auto -0.72rem auto 100%;
              top: 50%;
              width: 0.72rem;
              height: 4px;
              background: var(--outline);
              transform: translateY(-50%);
            }}

            .slot:nth-last-child(-n + 1)::after,
            .slot[style*="--column: 4"]::after {{
              display: none;
            }}

            .slot__headline {{
              display: flex;
              align-items: center;
              gap: 0.55rem;
              min-width: 0;
            }}

            .slot h3 {{
              font-size: 0.92rem;
              text-transform: uppercase;
              line-height: 1.05;
            }}

            .slot__metric {{
              font-weight: 700;
              line-height: 1.15;
              color: color-mix(in oklch, var(--ink) 84%, var(--muted) 16%);
            }}

            .slot__subtext,
            .slot__note {{
              font-size: 0.68rem;
              line-height: 1.2;
              color: color-mix(in oklch, var(--muted) 76%, var(--ink) 24%);
            }}

            .duel-row {{
              display: grid;
              grid-template-columns: auto minmax(0, 1fr) auto;
              gap: 0.35rem;
              align-items: center;
              padding: 0.2rem 0.25rem;
              border: 2px solid transparent;
              min-width: 0;
            }}

            .duel-row--favorite {{
              background: color-mix(in oklch, var(--gold) 18%, var(--screen));
              border-color: var(--outline);
            }}

            .duel-row__name {{
              font-weight: 700;
              line-height: 1.05;
              min-width: 0;
              font-size: 0.88rem;
              overflow-wrap: anywhere;
            }}

            .duel-row__stat {{
              font-family: "Silkscreen", monospace;
              font-size: 0.62rem;
            }}

            .seed-chip {{
              display: inline-grid;
              place-items: center;
              min-width: 1.65rem;
              height: 1.65rem;
              padding: 0 0.25rem;
              border: 2px solid var(--outline);
              font-family: "Silkscreen", monospace;
              font-size: 0.65rem;
              background: color-mix(in oklch, var(--screen) 70%, var(--gold) 30%);
            }}

            .boss-board {{
              display: grid;
              gap: 1rem;
              border: 4px solid var(--outline);
              background:
                linear-gradient(180deg, color-mix(in oklch, var(--gold) 18%, var(--screen)), color-mix(in oklch, var(--gold) 5%, var(--screen)));
              padding: 0.85rem;
              box-shadow: 9px 9px 0 var(--shadow);
              align-content: start;
              height: 100%;
            }}

            .boss-board__hero {{
              display: grid;
              gap: 0.7rem;
              border: 4px solid var(--outline);
              padding: 1rem;
              background: color-mix(in oklch, var(--gold) 18%, var(--screen));
            }}

            .boss-board__hero h2 {{
              font-size: clamp(1.4rem, 2vw, 2.35rem);
              text-transform: uppercase;
            }}

            .boss-board__hero p {{
              color: color-mix(in oklch, var(--ink) 85%, var(--muted) 15%);
            }}

            .boss-board__badge {{
              width: fit-content;
              border: 3px solid var(--outline);
              padding: 0.35rem 0.55rem;
              font-family: "Silkscreen", monospace;
              font-size: 0.75rem;
              background: color-mix(in oklch, var(--gold) 26%, var(--screen));
            }}

            .leaderboard {{
              display: grid;
              gap: 0.65rem;
              list-style: none;
              padding: 0;
              margin: 0;
            }}

            .leaderboard__row {{
              display: grid;
              grid-template-columns: auto minmax(0, 1fr) auto;
              align-items: center;
              gap: 0.7rem;
              padding: 0.55rem 0.7rem;
              border: 3px solid var(--outline);
              background: color-mix(in oklch, var(--screen) 88%, white 12%);
            }}

            .leaderboard__rank {{
              font-family: "Silkscreen", monospace;
              font-size: 0.75rem;
              color: var(--gold-deep);
            }}

            .leaderboard__name {{
              font-weight: 700;
            }}

            .leaderboard__stat {{
              font-family: "Silkscreen", monospace;
              font-size: 0.75rem;
            }}

            .showdowns {{
              display: grid;
              gap: 0.75rem;
            }}

            .showdown {{
              display: grid;
              gap: 0.55rem;
              border: 3px solid var(--outline);
              background: color-mix(in oklch, var(--screen) 88%, var(--gold) 12%);
              padding: 0.75rem;
            }}

            .showdown__vs {{
              display: flex;
              justify-content: space-between;
              gap: 0.5rem;
              font-family: "Silkscreen", monospace;
              font-size: 0.68rem;
              text-transform: uppercase;
            }}

            .showdown__divider {{
              color: var(--muted);
            }}

            .showdown__teams {{
              display: grid;
              gap: 0.55rem;
            }}

            .showdown__teams div {{
              display: grid;
              gap: 0.15rem;
            }}

            .showdown__teams span,
            .showdown__favorite,
            .boss-footer {{
              color: color-mix(in oklch, var(--ink) 80%, var(--muted) 20%);
              font-size: 0.84rem;
            }}

            .blink {{
              animation: blink 1.2s steps(2, end) infinite;
            }}

            @keyframes blink {{
              0%, 49% {{ opacity: 1; }}
              50%, 100% {{ opacity: 0.45; }}
            }}

            @media (max-width: 1500px) {{
              .arena {{
                grid-template-columns: repeat(2, minmax(0, 1fr));
              }}

              .boss-board {{
                grid-column: 1 / -1;
                order: -1;
                height: auto;
              }}
            }}

            @media (max-width: 980px) {{
              .arena {{
                grid-template-columns: 1fr;
              }}

              .masthead {{
                grid-template-columns: 1fr;
              }}

              .rail {{
                grid-template-columns: 1fr;
              }}

              .region__legend {{
                display: none;
              }}

              .region__grid {{
                grid-template-columns: 1fr;
                grid-template-rows: none;
                min-height: auto;
              }}

              .slot {{
                grid-column: auto;
                grid-row: auto;
              }}

              .slot::after {{
                display: none;
              }}
            }}
          </style>
        </head>
        <body>
          <div class="cabinet">
            <main class="screen">
              <section class="masthead">
                <div class="title-block">
                  <p class="title-block__eyebrow">{season_label} Monte Carlo arcade board</p>
                  <h1>2026 bracket boss rush</h1>
                  <p class="title-block__subhead">A retro 8-bit readout of the current tournament forecast. Openers show first-round win odds, each lane promotes the most likely survivor, and the center cabinet tracks the title race after {simulation_count:,} simulations.</p>
                </div>
                <aside class="marquee">
                  <div class="marquee__board">
                    <div class="marquee__line"><span>host city</span><span>{host_city}</span></div>
                    <div class="marquee__line"><span>efficiency feed</span><span>{escape(efficiency_note)}</span></div>
                    <div class="marquee__line"><span>top boss</span><span>{escape(top_seed.name)} {_format_pct(top_seed.champion_pct)}</span></div>
                    <div class="marquee__line blink"><span>status</span><span>press start to sim again</span></div>
                  </div>
                </aside>
              </section>

              <section class="arena">
                <div class="rail">{left_panels}</div>

                <section class="boss-board">
                  <div class="boss-board__hero">
                    <p class="boss-board__eyebrow">Boss podium</p>
                    <h2>{escape(top_seed.name)}</h2>
                    <div class="boss-board__badge">{_format_pct(top_seed.champion_pct)} title odds</div>
                    <p>{_format_pct(top_seed.final4_pct)} to make the Final Four · {_format_pct(top_seed.championship_pct)} to reach the title game · power {int(round(top_seed.rating))}</p>
                  </div>

                  <div>
                    <p class="boss-board__eyebrow">Top contenders</p>
                    <ol class="leaderboard">{_render_leaderboard(leaderboard)}</ol>
                  </div>

                  <div class="showdowns">
                    <p class="boss-board__eyebrow">Final Four lanes</p>
                    {_render_final_four_pairings(pairings, bosses)}
                  </div>

                  <p class="boss-footer">Graphic source: <code>monte_carlo_tourney_results.csv</code>, <code>combined_ratings.csv</code>, and the processed bracket tables for {season_label}. The cabinet keeps the bracket readable on mobile by collapsing into a stacked tournament board.</p>
                </section>

                <div class="rail">{right_panels}</div>
              </section>
            </main>
          </div>
        </body>
        </html>
        """
    ).strip() + "\n"


def render_arcade_bracket(
    season: int = DEFAULT_SEASON,
    processed_root: Path | None = None,
    output_root: Path | None = None,
    destination: Path | None = None,
) -> Path:
    processed_root = processed_root or processed_dir(season)
    output_root = output_root or output_dir(season)
    destination = destination or (output_root / f"retro_bracket_{season}.html")

    metrics, round64, first_four, metadata, simulation_count, efficiency_source = _load_inputs(
        season=season,
        processed_root=processed_root,
        output_root=output_root,
    )
    play_in_lookup = _build_play_in_lookup(first_four)

    panel_markup: dict[str, str] = {}
    bosses: dict[str, TeamMetrics] = {}
    for region in ("East", "South", "West", "Midwest"):
        markup, region_boss = _render_region_panel(
            region=region,
            region_rows=round64[round64["region"] == region],
            metrics=metrics,
            play_in_lookup=play_in_lookup,
        )
        panel_markup[region] = markup
        bosses[region] = region_boss

    leaderboard = sorted(metrics.values(), key=lambda item: (item.champion_pct, item.championship_pct, item.final4_pct), reverse=True)[:8]
    destination.parent.mkdir(parents=True, exist_ok=True)
    document = _build_document(
        season=season,
        simulation_count=simulation_count,
        efficiency_source=efficiency_source,
        metadata=metadata,
        left_panels=panel_markup["East"] + panel_markup["South"],
        right_panels=panel_markup["West"] + panel_markup["Midwest"],
        bosses=bosses,
        leaderboard=leaderboard,
        favicon_tags=favicon_head_tags(destination),
    )
    destination.write_text(document, encoding="utf-8")
    return destination
