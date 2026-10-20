# TASKS.md — Acosign

Rule: the agent works on ONE unchecked task at a time, then stops and reports.

## Phase 1 — Fingerprint Engine (Oct 20)
- [ ] P1.1 Scaffold audit + config + smoke test
- [ ] P1.2 app/engine/fingerprint.py: load audio (mono, SAMPLE_RATE) + spectrogram
- [ ] P1.3 Peak detection (local maxima, MIN_AMPLITUDE threshold)
- [ ] P1.4 Hash generation (anchor + FAN_OUT targets → (f1, f2, Δt) hash)
- [ ] P1.5 app/engine/matcher.py: offset voting (db_time - clip_time histogram)
- [ ] P1.6 Unit tests: determinism, clipped clip, noisy clip, unrelated audio rejected
- [ ] P1.7 docs/architecture.md: engine section

## Phase 2 — Database + API (Oct 21)
- [ ] P2.1 SQLAlchemy models: tracks (content_id, title, owner), fingerprints (hash, track_id, offset)
- [ ] P2.2 Repository functions: insert track + bulk insert hashes, lookup by hashes
- [ ] P2.3 POST /register (upload → fingerprint → store → return Content ID)
- [ ] P2.4 POST /identify (clip → hashes → match → track/owner/confidence)
- [ ] P2.5 GET /tracks, GET /health
- [ ] P2.6 API tests (httpx TestClient) incl. bad file, empty file, no match
- [ ] P2.7 docs/api.md

## Phase 3 — Demo + Deployment (Oct 22)
- [ ] P3.1 ui/app.py: Register page (upload + metadata)
- [ ] P3.2 ui/app.py: Identify page (upload + mic recording)
- [ ] P3.3 docker-compose: db + api + ui, healthchecks, .env wiring
- [ ] P3.4 Clean-machine test: `docker compose up` from fresh clone
- [ ] P3.5 README final (name, setup, API examples, screenshots)
- [ ] P3.6 FREEZE: no new features after this

## Phase 4 — Test & Polish (Oct 23–24)
- [ ] Noise robustness, clip-length limits, false-positive check
- [ ] Bug fixes only, demo rehearsal, backup screen recording

## Oct 25 — Submit. No coding.