from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ncaa_preds26.constants import REGIONS, ROUND64_SEED_ORDER
from ncaa_preds26.naming import canonical_team_id
from ncaa_preds26.simulate import ROUND_COLUMNS, simulate_bracket, simulate_bracket_details


class SimulationTests(unittest.TestCase):
    def test_simulation_is_deterministic_and_monotonic(self) -> None:
        bracket_rows = []
        ratings_rows = []
        rating_value = 3000.0

        for region in REGIONS:
            for matchup_order, (seed_top, seed_bottom) in enumerate(ROUND64_SEED_ORDER, start=1):
                top_name = f"{region} Top {matchup_order}"
                bottom_name = f"{region} Bottom {matchup_order}"
                top_id = canonical_team_id(top_name)
                bottom_id = canonical_team_id(bottom_name)
                bracket_rows.append(
                    {
                        "season": 2026,
                        "region": region,
                        "matchup_order": matchup_order,
                        "seed_top": seed_top,
                        "team_top": top_id,
                        "seed_bottom": seed_bottom,
                        "team_bottom": bottom_id,
                        "play_in_group_top": None,
                        "play_in_group_bottom": None,
                    }
                )
                ratings_rows.append({"team_id_canon": top_id, "Team": top_name, "blended_elo_scale": rating_value})
                ratings_rows.append({"team_id_canon": bottom_id, "Team": bottom_name, "blended_elo_scale": rating_value - 100})
                rating_value -= 10

        bracket_round64 = pd.DataFrame(bracket_rows)
        first_four = pd.DataFrame(
            columns=["group_id", "region", "seed", "slot_side", "team_a", "team_b", "team_a_id_canon", "team_b_id_canon"]
        )
        ratings = pd.DataFrame(ratings_rows)

        result_one = simulate_bracket(bracket_round64, first_four, ratings, sims=25, seed=7).reset_index(drop=True)
        result_two = simulate_bracket(bracket_round64, first_four, ratings, sims=25, seed=7).reset_index(drop=True)

        pd.testing.assert_frame_equal(result_one, result_two)
        self.assertTrue((result_one["R64"] == 25).all())
        for column_left, column_right in zip(ROUND_COLUMNS[1:], ROUND_COLUMNS[:-1]):
            self.assertTrue((result_one[column_left] <= result_one[column_right]).all())

    def test_matchup_summary_is_emitted_with_expected_columns(self) -> None:
        bracket_rows = []
        ratings_rows = []
        rating_value = 3000.0

        for region in REGIONS:
            for matchup_order, (seed_top, seed_bottom) in enumerate(ROUND64_SEED_ORDER, start=1):
                top_name = f"{region} Top {matchup_order}"
                bottom_name = f"{region} Bottom {matchup_order}"
                top_id = canonical_team_id(top_name)
                bottom_id = canonical_team_id(bottom_name)
                bracket_rows.append(
                    {
                        "season": 2026,
                        "region": region,
                        "matchup_order": matchup_order,
                        "seed_top": seed_top,
                        "team_top": top_id,
                        "seed_bottom": seed_bottom,
                        "team_bottom": bottom_id,
                        "play_in_group_top": None,
                        "play_in_group_bottom": None,
                    }
                )
                ratings_rows.append({"team_id_canon": top_id, "Team": top_name, "blended_elo_scale": rating_value})
                ratings_rows.append({"team_id_canon": bottom_id, "Team": bottom_name, "blended_elo_scale": rating_value - 100})
                rating_value -= 10

        bracket_round64 = pd.DataFrame(bracket_rows)
        first_four = pd.DataFrame(
            columns=["group_id", "region", "seed", "slot_side", "team_a", "team_b", "team_a_id_canon", "team_b_id_canon"]
        )
        ratings = pd.DataFrame(ratings_rows)

        _, matchup_summary = simulate_bracket_details(bracket_round64, first_four, ratings, sims=25, seed=7)

        self.assertFalse(matchup_summary.empty)
        self.assertTrue({"round", "matchup_count", "team_a_win_pct_when_met", "team_b_win_pct_when_met"}.issubset(matchup_summary.columns))
        self.assertTrue((matchup_summary["matchup_count"] <= 25).all())


if __name__ == "__main__":
    unittest.main()
