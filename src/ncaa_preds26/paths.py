from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PACKAGE_ROOT.parent
APP_ROOT = SRC_ROOT.parent
DATA_ROOT = APP_ROOT / "data"


def raw_dir(season: int) -> Path:
    return DATA_ROOT / "raw" / str(season)


def processed_dir(season: int) -> Path:
    return DATA_ROOT / "processed" / str(season)


def output_dir(season: int) -> Path:
    return DATA_ROOT / "output" / str(season)


def manual_dir(season: int) -> Path:
    return DATA_ROOT / "manual" / str(season)


def report_path(filename: str) -> Path:
    return APP_ROOT / filename


def ensure_directories(season: int) -> None:
    for path in (raw_dir(season), processed_dir(season), output_dir(season), manual_dir(season)):
        path.mkdir(parents=True, exist_ok=True)
