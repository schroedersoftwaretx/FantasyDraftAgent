# Fantasy Draft Assistant

Phase 1 foundation for a fantasy football draft assistant.

This project builds:
- a SQLAlchemy database schema for players, stats, projections, and VORP
- ingestion pipelines for historical stats, ADP, and projections
- VORP + tiering model outputs for draft-ready rankings

## Quickstart

1. Install dependencies:
   - `uv sync` (recommended) or `pip install -e .`
2. Copy env template:
   - `copy .env.example .env` (Windows) or `cp .env.example .env`
3. Run the pipeline:
   - `python -m src.pipeline.run`

The pipeline writes ranked, tiered players into `vorp_scores`.

## Season defaults

- Default target season is `2026`.
- Historical guidance defaults to `2023-2025`.
- If an external 2026 projection source is unavailable, the pipeline falls back to historical data (with 2025 as the primary prior season signal).