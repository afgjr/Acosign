# AGENT.md — Acosign

## Mission
Audio fingerprinting + Content ID platform. Upload audio → fingerprint → store
with Content ID → identify unknown clips via API.

## Stack (do NOT change without asking)
FastAPI, Librosa/NumPy/SciPy, PostgreSQL (SQLAlchemy), Streamlit, Docker Compose.
Python 3.11. Type hints everywhere.

## Reference
Algorithm reference: github.com/worldveil/dejavu (peak finding → hash pairs →
offset voting). Reimplement; do not copy code.

## Structure
app/
  main.py        # FastAPI entrypoint
  api/           # routers + pydantic schemas
  core/          # config.py (ALL tunables), logging
  db/            # SQLAlchemy models, session, repository functions
  engine/        # fingerprint.py (spectrogram, peaks, hashes) + matcher.py (offset voting)
ui/app.py        # Streamlit; talks to API over HTTP only, never imports app/
tests/           # pytest, mirrors app/ layout (tests/engine/, tests/api/)
data/samples/    # test audio (small files only)
docs/            # architecture.md, api.md, testing.md
Dockerfile (API), Dockerfile.ui (Streamlit), docker-compose.yml

## Rules
1. Fingerprint code must be pure and deterministic (same input → same hashes).
2. All magic numbers live in app/core/config.py.
3. Every new module ships with pytest tests in the same change.
4. Never hardcode secrets; use .env + .env.example.
5. Small steps: implement ONLY the task requested, then stop and report.
6. After each task: run `pytest -q`, show the output, list files changed.
7. Do not refactor unrelated files. Do not add dependencies without saying why.
8. app/engine/ must not import from app/db or app/api (pure functions).
9. ui/ must not import from app/. HTTP only.
10. Existing files are not rewritten without being listed first.
11.  Target runtime is Python 3.12 (Docker/CI). Never use features or pins that break on 3.12.
12. After finishing a task, tick its checkbox in TASKS.md.
13. Tests use synthetic audio generated with numpy. Never depend on real song files.

## Definition of Done (per task)
- Tests pass, type hints present, docstrings on public functions
- docs/ updated if behavior or API changed
- A short "How to verify manually" section in the reply

## Current phase
Phase 1: fingerprint engine in app/engine/ (see TASKS.md)