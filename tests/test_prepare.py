from __future__ import annotations

import sys
import tempfile
import unittest
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ncaa_preds26.prepare import prepare_datasets


ELO_HTML = """
<table>
  <tr><th>Team</th><th>ELO</th></tr>
  <tr><td>Alpha</td><td>2100</td></tr>
  <tr><td>Beta</td><td>2000</td></tr>
  <tr><td>Gamma</td><td>2080</td></tr>
  <tr><td>Delta</td><td>1980</td></tr>
  <tr><td>Epsilon</td><td>2070</td></tr>
  <tr><td>Iota</td><td>1900</td></tr>
  <tr><td>Kappa</td><td>1890</td></tr>
  <tr><td>Eta</td><td>2060</td></tr>
  <tr><td>Theta</td><td>1880</td></tr>
</table>
"""

EFFICIENCY_HTML = """
<table>
  <tr><th>Team</th><th>NetRtg</th></tr>
  <tr><td>Alpha</td><td>35.0</td></tr>
  <tr><td>Beta</td><td>10.0</td></tr>
  <tr><td>Gamma</td><td>34.0</td></tr>
  <tr><td>Delta</td><td>9.5</td></tr>
  <tr><td>Epsilon</td><td>33.5</td></tr>
  <tr><td>Iota</td><td>8.0</td></tr>
  <tr><td>Kappa</td><td>7.5</td></tr>
  <tr><td>Eta</td><td>32.5</td></tr>
  <tr><td>Theta</td><td>7.0</td></tr>
</table>
"""

AP_LATEST_HTML = """
<table>
  <tr><th>Rank</th><th>Team</th><th>Points</th></tr>
  <tr><td>1</td><td>Alpha</td><td>1500</td></tr>
  <tr><td>2</td><td>Gamma</td><td>1400</td></tr>
  <tr><td>3</td><td>Epsilon</td><td>1300</td></tr>
  <tr><td>4</td><td>Eta</td><td>1200</td></tr>
</table>
"""

AP_PRESEASON_HTML = """
<table>
  <tr><th>Rank</th><th>Team</th></tr>
  <tr><td>1</td><td>Gamma</td></tr>
  <tr><td>2</td><td>Alpha</td></tr>
  <tr><td>3</td><td>Epsilon</td></tr>
</table>
"""

REPORT_TEXT = """
### East region
(1) Alpha vs (16) Beta

### West region
(1) Gamma vs (16) Delta

### South region
(1) Epsilon vs (16) Iota / Kappa *(First Four matchup)*

### Midwest region
(1) Eta vs (16) Theta

**Final Four host city shown on the official bracket:** Testville.
"""


class PrepareDatasetTests(unittest.TestCase):
    def test_prepare_builds_processed_csvs_from_local_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            raw_dir = temp_dir / "raw"
            processed_dir = temp_dir / "processed"
            manual_dir = temp_dir / "manual"
            raw_dir.mkdir()
            processed_dir.mkdir()
            manual_dir.mkdir()

            (raw_dir / "elo.html").write_text(ELO_HTML, encoding="utf-8")
            (raw_dir / "kenpom.html").write_text(EFFICIENCY_HTML, encoding="utf-8")
            (raw_dir / "ap_latest.html").write_text(AP_LATEST_HTML, encoding="utf-8")
            (raw_dir / "ap_preseason.html").write_text(AP_PRESEASON_HTML, encoding="utf-8")
            report_path = temp_dir / "report.md"
            report_path.write_text(REPORT_TEXT, encoding="utf-8")

            outputs = prepare_datasets(
                season=2026,
                raw_root=raw_dir,
                processed_root=processed_dir,
                manual_root=manual_dir,
                report_file=report_path,
            )

            ratings_inputs = pd.read_csv(outputs["ratings_inputs"])
            bracket_field = pd.read_csv(outputs["bracket_field"])
            first_four = pd.read_csv(outputs["first_four"])
            join_qa = pd.read_csv(outputs["join_qa"])
            bracket_meta = json.loads(outputs["bracket_metadata"].read_text(encoding="utf-8"))

            self.assertEqual(len(bracket_field), 9)
            self.assertEqual(len(first_four), 1)
            self.assertEqual(len(ratings_inputs), 9)
            self.assertFalse(join_qa["needs_override"].any())
            self.assertIn("team_a_id_canon", first_four.columns)
            self.assertIn("team_top_name", pd.read_csv(outputs["bracket_round64"]).columns)
            self.assertEqual(bracket_meta["final_four_pairings"], [["East", "South"], ["Midwest", "West"]])


if __name__ == "__main__":
    unittest.main()
