from __future__ import annotations

DEFAULT_SEASON = 2026

AP_LATEST_WEEK = {
    2026: 20,
}

PRESEASON_AP_URL = {
    2026: "https://www.collegepollarchive.com/basketball/men/ap/seasons.cfm?appollid=1302",
}

BRACKET_REPORT_FILE = {
    2026: "ncaa_26.md",
}

ELO_URL_TEMPLATE = "https://www.warrennolan.com/basketball/{season}/elo"
AP_WEEK_URL_TEMPLATE = "https://www.warrennolan.com/basketball/{season}/polls/week/{week}"
KENPOM_URL = "https://kenpom.com/index.php"
TORVIK_URL_TEMPLATE = "https://barttorvik.com/{season}_team_results.json"

RATING_WEIGHTS = {
    "elo_norm": 0.70,
    "efficiency_rating_norm": 0.15,
    "ap_latest_inverted_norm": 0.10,
    "ap_preseason_inverted_norm": 0.05,
}

LOGISTIC_K = 0.004

REGIONS = ("East", "West", "South", "Midwest")

ROUND64_SEED_ORDER = (
    (1, 16),
    (8, 9),
    (5, 12),
    (4, 13),
    (6, 11),
    (3, 14),
    (7, 10),
    (2, 15),
)

FINAL_FOUR_PAIRINGS = (
    ("East", "South"),
    ("Midwest", "West"),
)
