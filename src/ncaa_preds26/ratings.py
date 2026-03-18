from __future__ import annotations

from pathlib import Path

import pandas as pd
from sklearn.preprocessing import StandardScaler

from .constants import DEFAULT_SEASON, RATING_WEIGHTS
from .paths import output_dir, processed_dir


def build_ratings_table(ratings_inputs: pd.DataFrame) -> pd.DataFrame:
    frame = ratings_inputs.copy()
    required = {"Team", "elo", "efficiency_rating"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"ratings_inputs is missing required columns: {sorted(missing)}")

    frame = frame.dropna(subset=["elo", "efficiency_rating"]).copy()
    frame["ap_latest_rank"] = frame["ap_latest_rank"].fillna(26)
    frame["ap_preseason_rank"] = frame["ap_preseason_rank"].fillna(26)
    frame["ap_latest_inverted"] = -frame["ap_latest_rank"]
    frame["ap_preseason_inverted"] = -frame["ap_preseason_rank"]

    feature_columns = [
        "elo",
        "efficiency_rating",
        "ap_latest_inverted",
        "ap_preseason_inverted",
    ]
    scaled_names = [
        "elo_norm",
        "efficiency_rating_norm",
        "ap_latest_inverted_norm",
        "ap_preseason_inverted_norm",
    ]
    scaler = StandardScaler()
    frame[scaled_names] = scaler.fit_transform(frame[feature_columns])

    frame["blended"] = (
        RATING_WEIGHTS["elo_norm"] * frame["elo_norm"]
        + RATING_WEIGHTS["efficiency_rating_norm"] * frame["efficiency_rating_norm"]
        + RATING_WEIGHTS["ap_latest_inverted_norm"] * frame["ap_latest_inverted_norm"]
        + RATING_WEIGHTS["ap_preseason_inverted_norm"] * frame["ap_preseason_inverted_norm"]
    )

    mu_blend = frame["blended"].mean()
    std_blend = frame["blended"].std(ddof=1)
    mu_elo = frame["elo"].mean()
    std_elo = frame["elo"].std(ddof=1)
    if std_blend == 0 or pd.isna(std_blend):
        frame["blended_elo_scale"] = mu_elo
    else:
        frame["blended_elo_scale"] = ((frame["blended"] - mu_blend) / std_blend) * std_elo + mu_elo

    frame = frame.sort_values("blended_elo_scale", ascending=False).reset_index(drop=True)
    return frame


def build_ratings(season: int = DEFAULT_SEASON, processed_root: Path | None = None, output_root: Path | None = None) -> dict[str, Path]:
    processed_root = processed_root or processed_dir(season)
    output_root = output_root or output_dir(season)
    ratings_inputs = pd.read_csv(processed_root / "ratings_inputs.csv")
    combined = build_ratings_table(ratings_inputs)

    small = combined[["Team", "elo", "blended", "blended_elo_scale"]].copy()
    small = small.rename(
        columns={
            "elo": "ELO",
            "blended": "Blended",
            "blended_elo_scale": "Blended_EloScale",
        }
    )

    outputs = {
        "combined_ratings": output_root / "combined_ratings.csv",
        "combined_ratings_small": output_root / "combined_ratings_small.csv",
    }
    combined.to_csv(outputs["combined_ratings"], index=False)
    small.to_csv(outputs["combined_ratings_small"], index=False)
    return outputs
