from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ncaa_preds26.report import parse_report_file


class ReportParserTests(unittest.TestCase):
    def test_report_parses_2026_field_and_unresolved_play_ins(self) -> None:
        field, round64, first_four, metadata = parse_report_file(ROOT / "ncaa_26.md", season=2026)

        self.assertEqual(len(round64), 32)
        self.assertEqual(len(field), 68)
        self.assertEqual(len(first_four), 2)
        self.assertEqual(metadata["host_city"], "Indianapolis")

        south_top = round64[(round64["region"] == "South") & (round64["matchup_order"] == 1)].iloc[0]
        self.assertTrue(pd.isna(south_top["team_bottom"]))
        self.assertEqual(south_top["play_in_group_bottom"], "south_16_1_bottom")

        west_play_in_winner = round64[(round64["region"] == "West") & (round64["matchup_order"] == 5)].iloc[0]
        self.assertEqual(west_play_in_winner["team_bottom"], "Texas")
        self.assertTrue(pd.isna(west_play_in_winner["play_in_group_bottom"]))


if __name__ == "__main__":
    unittest.main()
