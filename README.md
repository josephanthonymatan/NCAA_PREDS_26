# NCAA_PREDS_26

Python CLI and library for rebuilding the 2026 NCAA men's tournament model without notebooks.

## Commands

Run from `NCAA_PREDS_26/` after installing dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
ncaa26 fetch --season 2026
ncaa26 prepare --season 2026
ncaa26 ratings --season 2026
ncaa26 simulate --season 2026 --sims 100000 --seed 42
```

Or run directly from source:

```bash
PYTHONPATH=src python -m ncaa_preds26 run-all --season 2026 --sims 100000 --seed 42
```

## Data Layout

- `data/raw/2026/`: fetched source artifacts and metadata
- `data/manual/2026/`: manual alias overrides
- `data/processed/2026/`: normalized bracket and ratings inputs
- `data/output/2026/`: combined ratings and tournament odds

The bracket pipeline can bootstrap from `ncaa_26.md` when an official bracket artifact is not yet available locally.

## Hosted Artifact

The current static site entrypoint is:

- `data/output/2026/matchup_lab_2026.html`

Supporting artifacts:

- `data/output/2026/most_unlikely_bracket_2026.html`
- `data/output/2026/retro_bracket_2026.html`

## Vercel

This repo is set up to deploy as a static Vercel project.

- `/` serves the matchup lab
- `/rarest` serves the rarest sampled bracket view
- `/retro` serves the retro bracket graphic

The routes are configured in `vercel.json`. Deployment only needs the generated HTML in `data/output/2026/`, so `.vercelignore` excludes the dogfood evidence and local pipeline files from the upload.
