from __future__ import annotations

from pathlib import Path

from .fetch import fetch_sources
from .prepare import prepare_datasets
from .ratings import build_ratings
from .render_bracket import render_arcade_bracket
from .render_matchup_explorer import render_matchup_explorer
from .simulate import simulate_tournament


def run_all(season: int = 2026, sims: int = 100000, seed: int = 42) -> dict[str, Path]:
    artifacts = fetch_sources(season=season)
    prepared = prepare_datasets(season=season)
    ratings = build_ratings(season=season)
    simulation = simulate_tournament(season=season, sims=sims, seed=seed)
    retro_bracket = render_arcade_bracket(season=season)
    matchup_lab = render_matchup_explorer(season=season)
    return {
        **artifacts,
        **prepared,
        **ratings,
        "simulation": simulation,
        "retro_bracket": retro_bracket,
        "matchup_lab": matchup_lab,
    }
