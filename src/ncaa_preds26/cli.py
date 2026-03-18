from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .fetch import fetch_sources
from .pipeline import run_all
from .prepare import prepare_datasets
from .ratings import build_ratings
from .render_bracket import render_arcade_bracket
from .render_matchup_explorer import render_matchup_explorer
from .render_rarest_bracket import render_rarest_bracket
from .simulate import simulate_tournament


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--season", type=int, default=2026, help="Season to process.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="2026 NCAA tournament model pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch", help="Fetch source artifacts")
    _add_common_arguments(fetch_parser)

    prepare_parser = subparsers.add_parser("prepare", help="Normalize raw artifacts into processed datasets")
    _add_common_arguments(prepare_parser)

    ratings_parser = subparsers.add_parser("ratings", help="Build blended ratings from processed inputs")
    _add_common_arguments(ratings_parser)

    simulate_parser = subparsers.add_parser("simulate", help="Run Monte Carlo tournament simulations")
    _add_common_arguments(simulate_parser)
    simulate_parser.add_argument("--sims", type=int, default=100000, help="Number of Monte Carlo simulations.")
    simulate_parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic results.")

    render_parser = subparsers.add_parser("render-bracket", help="Render a retro arcade HTML bracket graphic")
    _add_common_arguments(render_parser)
    render_parser.add_argument("--output", type=Path, default=None, help="Optional output path for the HTML artifact.")

    matchup_lab_parser = subparsers.add_parser("render-matchup-lab", help="Render a local interactive matchup explorer")
    _add_common_arguments(matchup_lab_parser)
    matchup_lab_parser.add_argument("--output", type=Path, default=None, help="Optional output path for the HTML artifact.")

    rarest_bracket_parser = subparsers.add_parser("render-rarest-bracket", help="Render the rarest full bracket from the saved Monte Carlo run")
    _add_common_arguments(rarest_bracket_parser)
    rarest_bracket_parser.add_argument("--sims", type=int, default=100000, help="Number of Monte Carlo simulations to replay.")
    rarest_bracket_parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic results.")
    rarest_bracket_parser.add_argument("--output", type=Path, default=None, help="Optional output path for the HTML artifact.")

    run_all_parser = subparsers.add_parser("run-all", help="Run fetch, prepare, ratings, and simulate")
    _add_common_arguments(run_all_parser)
    run_all_parser.add_argument("--sims", type=int, default=100000, help="Number of Monte Carlo simulations.")
    run_all_parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic results.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "fetch":
        artifacts = fetch_sources(season=args.season)
        for name, path in artifacts.items():
            print(f"{name}: {path}")
        return 0
    if args.command == "prepare":
        outputs = prepare_datasets(season=args.season)
        for name, path in outputs.items():
            print(f"{name}: {path}")
        return 0
    if args.command == "ratings":
        outputs = build_ratings(season=args.season)
        for name, path in outputs.items():
            print(f"{name}: {path}")
        preview = pd.read_csv(outputs["combined_ratings_small"]).head(10)
        print(preview.to_string(index=False))
        return 0
    if args.command == "simulate":
        output_path = simulate_tournament(season=args.season, sims=args.sims, seed=args.seed)
        preview = pd.read_csv(output_path).head(10)
        print(Path(output_path))
        print(preview.to_string(index=False))
        return 0
    if args.command == "render-bracket":
        output_path = render_arcade_bracket(season=args.season, destination=args.output)
        print(Path(output_path))
        return 0
    if args.command == "render-matchup-lab":
        output_path = render_matchup_explorer(season=args.season, destination=args.output)
        print(Path(output_path))
        return 0
    if args.command == "render-rarest-bracket":
        output_path = render_rarest_bracket(season=args.season, sims=args.sims, seed=args.seed, destination=args.output)
        print(Path(output_path))
        return 0
    if args.command == "run-all":
        outputs = run_all(season=args.season, sims=args.sims, seed=args.seed)
        for name, path in outputs.items():
            print(f"{name}: {path}")
        return 0
    parser.error(f"Unsupported command: {args.command}")
    return 2
