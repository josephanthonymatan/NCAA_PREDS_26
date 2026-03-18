from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ncaa_preds26.ratings import build_ratings_table


class RatingsTests(unittest.TestCase):
    def test_build_ratings_table_preserves_notebook_methodology(self) -> None:
        inputs = pd.DataFrame(
            [
                {
                    "season": 2026,
                    "team_id_canon": "alpha",
                    "Team": "Alpha",
                    "elo": 2100,
                    "efficiency_rating": 35.0,
                    "ap_latest_rank": 1.0,
                    "ap_preseason_rank": 2.0,
                    "efficiency_source": "kenpom",
                },
                {
                    "season": 2026,
                    "team_id_canon": "beta",
                    "Team": "Beta",
                    "elo": 2000,
                    "efficiency_rating": 20.0,
                    "ap_latest_rank": None,
                    "ap_preseason_rank": 10.0,
                    "efficiency_source": "kenpom",
                },
                {
                    "season": 2026,
                    "team_id_canon": "gamma",
                    "Team": "Gamma",
                    "elo": 1950,
                    "efficiency_rating": 15.0,
                    "ap_latest_rank": 12.0,
                    "ap_preseason_rank": None,
                    "efficiency_source": "kenpom",
                },
            ]
        )

        combined = build_ratings_table(inputs)

        self.assertEqual(combined.iloc[0]["Team"], "Alpha")
        beta = combined[combined["Team"] == "Beta"].iloc[0]
        gamma = combined[combined["Team"] == "Gamma"].iloc[0]
        self.assertEqual(beta["ap_latest_rank"], 26.0)
        self.assertEqual(gamma["ap_preseason_rank"], 26.0)
        self.assertIn("blended_elo_scale", combined.columns)
        self.assertTrue((combined["blended_elo_scale"].notna()).all())


if __name__ == "__main__":
    unittest.main()
