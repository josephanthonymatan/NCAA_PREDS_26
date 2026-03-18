from __future__ import annotations

import re
import unicodedata


def normalize_team_name(name: str) -> str:
    ascii_name = (
        unicodedata.normalize("NFKD", str(name))
        .encode("ascii", "ignore")
        .decode("ascii")
        .upper()
    )
    ascii_name = ascii_name.replace("&", " AND ")
    ascii_name = ascii_name.replace("/", " / ")
    ascii_name = re.sub(r"[.'’]", "", ascii_name)
    ascii_name = re.sub(r"[^A-Z0-9()/ -]+", " ", ascii_name)
    ascii_name = re.sub(r"\s+", " ", ascii_name)
    return ascii_name.strip()


def canonical_team_id(name: str) -> str:
    normalized = normalize_team_name(name).lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_")
