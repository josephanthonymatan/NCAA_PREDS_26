from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from .constants import (
    AP_LATEST_WEEK,
    AP_WEEK_URL_TEMPLATE,
    ELO_URL_TEMPLATE,
    KENPOM_URL,
    PRESEASON_AP_URL,
    TORVIK_URL_TEMPLATE,
)
from .paths import APP_ROOT, ensure_directories, raw_dir


@dataclass(frozen=True)
class SourceSpec:
    key: str
    url: str
    filename: str


USER_AGENT = "ncaa-preds26/0.1 (+local research pipeline)"


def _extract_bootstrap_urls() -> dict[str, str]:
    urls: dict[str, str] = {}
    for candidate in (APP_ROOT / "ncaa_26_links.md", APP_ROOT / "ncaa_26.md"):
        if not candidate.exists():
            continue
        text = candidate.read_text(encoding="utf-8")
        for match in re.findall(r"https?://[^\s)`>\"]+", text):
            if "warrennolan.com/basketball/2026/elo" in match:
                urls["elo"] = match
            elif "warrennolan.com/basketball/2026/polls/week/20" in match:
                urls["ap_latest"] = match
            elif "collegepollarchive.com" in match and "appollid=1302" in match:
                urls["ap_preseason"] = match
            elif "kenpom.com/index.php" in match:
                urls["kenpom"] = match
            elif "barttorvik.com/2026_team_results.json" in match:
                urls["torvik"] = match
            elif "ncaa.com/news/basketball-men/mml-official-bracket" in match:
                urls["bracket_article"] = match
            elif "ncaa.com/brackets/print/basketball-men/d1/2026" in match:
                urls["bracket_pdf"] = match
    return urls


def _save_artifact(path: Path, url: str, content: bytes, content_type: str | None) -> Path:
    path.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    metadata = {
        "source_url": url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "sha256": digest,
        "content_type": content_type,
        "filename": path.name,
    }
    path.with_suffix(path.suffix + ".meta.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _curl_download(url: str) -> tuple[bytes, str | None]:
    body = subprocess.run(
        ["curl", "-sS", "-L", url],
        capture_output=True,
        check=True,
    )
    content_type: str | None = None
    try:
        headers = subprocess.run(
            ["curl", "-sSI", "-L", url],
            capture_output=True,
            check=True,
            text=True,
        )
        for line in headers.stdout.splitlines():
            if line.lower().startswith("content-type:"):
                content_type = line.split(":", 1)[1].strip()
    except Exception:  # pragma: no cover - metadata only
        content_type = None
    return body.stdout, content_type


def _download(spec: SourceSpec, destination: Path, session: requests.Session) -> Path:
    output_path = destination / spec.filename
    try:
        content, content_type = _curl_download(spec.url)
    except Exception:
        try:
            response = session.get(spec.url, timeout=30)
            response.raise_for_status()
            content = response.content
            content_type = response.headers.get("Content-Type")
        except Exception:
            if output_path.exists():
                meta_path = output_path.with_suffix(output_path.suffix + ".meta.json")
                if not meta_path.exists():
                    _save_artifact(output_path, spec.url, output_path.read_bytes(), "cached/local")
                return output_path
            raise

    if spec.key == "kenpom":
        body = content.decode("utf-8", errors="ignore")
        if "Just a moment..." in body or "__cf_chl_" in body or "Enable JavaScript and cookies to continue" in body:
            if output_path.exists():
                return output_path
            raise RuntimeError("KenPom returned a Cloudflare challenge instead of ratings content")
    return _save_artifact(output_path, spec.url, content, content_type)


def fetch_sources(season: int = 2026) -> dict[str, Path]:
    ensure_directories(season)
    destination = raw_dir(season)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    bootstrap_urls = _extract_bootstrap_urls()

    artifacts: dict[str, Path] = {}
    specs = [
        SourceSpec("elo", bootstrap_urls.get("elo", ELO_URL_TEMPLATE.format(season=season)), "elo.html"),
        SourceSpec(
            "ap_latest",
            bootstrap_urls.get("ap_latest", AP_WEEK_URL_TEMPLATE.format(season=season, week=AP_LATEST_WEEK[season])),
            "ap_latest.html",
        ),
        SourceSpec("ap_preseason", bootstrap_urls.get("ap_preseason", PRESEASON_AP_URL[season]), "ap_preseason.html"),
    ]

    for spec in specs:
        artifacts[spec.key] = _download(spec, destination, session)

    optional_specs: list[SourceSpec] = []
    if "bracket_article" in bootstrap_urls:
        optional_specs.append(SourceSpec("bracket_article", bootstrap_urls["bracket_article"], "bracket_article.html"))
    if "bracket_pdf" in bootstrap_urls:
        optional_specs.append(SourceSpec("bracket_pdf", bootstrap_urls["bracket_pdf"], "bracket.pdf"))
    for spec in optional_specs:
        try:
            artifacts[spec.key] = _download(spec, destination, session)
        except Exception:  # pragma: no cover - best effort
            pass

    efficiency_specs = [
        SourceSpec("kenpom", bootstrap_urls.get("kenpom", KENPOM_URL), "kenpom.html"),
        SourceSpec("torvik", bootstrap_urls.get("torvik", TORVIK_URL_TEMPLATE.format(season=season)), "torvik.json"),
    ]
    last_error: Exception | None = None
    for spec in efficiency_specs:
        try:
            artifacts["efficiency"] = _download(spec, destination, session)
            artifacts["efficiency_source"] = destination / "efficiency_source.selected"
            artifacts["efficiency_source"].write_text(spec.key, encoding="utf-8")
            break
        except Exception as exc:  # pragma: no cover - exercised in live usage
            last_error = exc
    else:
        raise RuntimeError("Unable to fetch any efficiency source") from last_error

    return artifacts
