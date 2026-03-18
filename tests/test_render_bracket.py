from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ncaa_preds26.render_bracket import render_arcade_bracket
from ncaa_preds26.render_matchup_explorer import render_matchup_explorer
from ncaa_preds26.render_rarest_bracket import render_rarest_bracket


class RenderBracketTests(unittest.TestCase):
    def test_render_arcade_bracket_writes_html_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            destination = Path(temp_dir_name) / "retro.html"
            output_path = render_arcade_bracket(
                season=2026,
                processed_root=ROOT / "data" / "processed" / "2026",
                output_root=ROOT / "data" / "output" / "2026",
                destination=destination,
            )

            html = output_path.read_text(encoding="utf-8")
            self.assertEqual(output_path, destination)
            self.assertIn("2026 bracket boss rush", html.lower())
            self.assertIn("Duke", html)
            self.assertIn("East sector", html)
            self.assertIn("press start to sim again", html)

    def test_render_matchup_explorer_writes_local_interactive_artifact(self) -> None:
        output_root = ROOT / "data" / "output" / "2026"
        matchup_summary_path = output_root / "matchup_summary.csv"

        if not matchup_summary_path.exists():
            results = pd.read_csv(output_root / "monte_carlo_tourney_results.csv")
            results[["team_id_canon", "Team", "simulation_count"]].head(5).assign(
                round="Sweet16",
                team_a_id_canon=results.iloc[0]["team_id_canon"],
                team_a_name=results.iloc[0]["Team"],
                team_b_id_canon=results.iloc[1]["team_id_canon"],
                team_b_name=results.iloc[1]["Team"],
                matchup_count=1,
                matchup_pct=0.001,
                team_a_wins=1,
                team_b_wins=0,
                team_a_win_pct_when_met=100.0,
                team_b_win_pct_when_met=0.0,
            ).head(1).to_csv(matchup_summary_path, index=False)

        with tempfile.TemporaryDirectory() as temp_dir_name:
            destination = Path(temp_dir_name) / "matchup-lab.html"
            output_path = render_matchup_explorer(
                season=2026,
                processed_root=ROOT / "data" / "processed" / "2026",
                output_root=output_root,
                destination=destination,
            )

            html = output_path.read_text(encoding="utf-8")
            self.assertEqual(output_path, destination)
            self.assertIn("Build a smarter bracket by playing the odds.", html)
            self.assertIn("Michigan St.", html)
            self.assertIn("Round of 64", html)
            self.assertIn("Raw Elo", html)
            self.assertIn("https://github.com/josephanthonymatan", html)

    def test_render_rarest_bracket_writes_static_meta_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            destination = Path(temp_dir_name) / "rarest.html"
            output_path = render_rarest_bracket(
                season=2026,
                sims=64,
                seed=42,
                processed_root=ROOT / "data" / "processed" / "2026",
                output_root=ROOT / "data" / "output" / "2026",
                destination=destination,
            )

            html = output_path.read_text(encoding="utf-8")
            json_path = destination.with_suffix(".json")
            self.assertEqual(output_path, destination)
            self.assertTrue(json_path.exists())
            self.assertIn("most unlikely bracket", html.lower())
            self.assertIn("The games that made this bracket so unlikely", html)
            self.assertIn("Duke", html)


if __name__ == "__main__":
    unittest.main()
