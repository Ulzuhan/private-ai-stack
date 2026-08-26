# Changelog

All notable changes to private-ai-stack are documented here. The project follows Semantic
Versioning while it is pre-1.0: minor releases may change operational behavior, and patch
releases contain compatible fixes.

## [Unreleased]

## [0.2.0] - 2026-08-27

### Added

- The "Reed Documents" pipe: document Q&A inside the Open WebUI chat, with
  Reed as the only RAG pipeline. The pipe (`openwebui/reed_pipe.py`) appears
  as a selectable model, proxies Reed's `/v1/ask` so answers keep their
  calibrated generation, citation audit and honest refusals, and turns every
  returned source into a native, clickable citation card.
- `scripts/install-reed-pipe.sh`: installs or refreshes the pipe as code via
  Open WebUI's functions REST API — create/update/toggle/valves, never the
  destructive `/sync` — idempotently, and proves at the end that the pipe is
  selectable as a model. Authenticates with an admin API key from `.env`
  (`WEBUI_ADMIN_API_KEY`) or, as CI does, an email/password sign-in. The
  stack CI job runs it twice against the live stack on every change.
- `ENABLE_API_KEYS=true` in the Open WebUI service: upstream defaults it to
  false, and the documented install path needs personal API keys to exist.
  Nothing ships a key; each deployment creates its own.
- A browser E2E journey for the pipe (`tests/e2e/test_reed_pipe.py`): mints
  an admin API key, runs the installer exactly as a user would, picks "Reed
  Documents" in the model selector, asks about a document, and asserts the
  answer renders with native citation cards that expand and open. Selectors
  are verified against the pinned Open WebUI v0.11.0 sources; answer quality
  is never asserted — the tiny CI model proves the circuit only.
- The pipe short-circuits Open WebUI's background tasks (chat titles,
  follow-up suggestions) via `__task__` instead of spending a Reed lookup on
  each meta-prompt — they arrive through the selected model, which is the
  pipe.
- The CI compose override gives Reed a wider provider timeout
  (`REED_PROVIDER_TIMEOUT_SECONDS=240`): on the 4-vCPU runner, cold 0.8b
  generation exceeds Reed's calibrated 120 s default and `/v1/ask` answers
  502. Production keeps Reed's default.

- Documentation for the pipe, which the feature needed before it could be
  called shipped: what it is and how to install it in both READMEs, how it
  keeps the one-RAG-door rule in `docs/architecture.md`, and the admin API
  key — creating it, storing it, rotating it — in `docs/operations.md`, which
  had been describing the whole integration as a roadmap item while it sat in
  `main`.

### Changed

- Track Reed 0.6.0, and take the tmpfs budget it implies. Reed now bounds how
  many uploads may spool at once (`REED_MAX_CONCURRENT_UPLOADS`, default 4),
  because each in-flight upload holds two copies on the temporary filesystem
  and nothing stopped them from filling it. That bound only helps if `/tmp` is
  sized for it, so the stack's `REED_TMPFS_SIZE` default rises from 64 MiB to
  256 MiB: `2 x 25 MB x 4`. A tmpfs size is a cap, not a reservation, so the
  larger number costs nothing until the space is used. The release also stops
  shipping pip inside the Reed image — its vendored msgpack and setuptools
  were the last findings the image scan had to report — moves the base to
  Python 3.14.7, keeps the query embedding outside Reed's vector lock so asks,
  searches and ingestion stop queueing behind each other, heartbeats a queued
  SSE stream instead of letting it go silent, and stops publishing the version
  in the OpenAPI schema on a keyed deployment.
- Track Ollama 0.33.0. The pinning policy asks for the latest release; this
  one fixes nothing the scanner sees, and the allowlist says so rather than
  implying a security win: 0.32.5 and 0.33.0 report the same 38 Go findings,
  scanned side by side.
- Rebuild the Trivy allowlist against what the images report today, which is
  what put the weekly rescan back in the green after three red Mondays. Every
  entry was re-derived from a scan rather than carried forward: five stale
  Qdrant entries are gone, and the advisories that appeared since the last
  review are named with their exposure — util-linux `mount` TOCTOUs in a
  container that mounts nothing, an OpenSSL QUIC-server DoS in a service that
  speaks HTTP and gRPC. Reed 0.6.0 needs no entries at all.

## [0.1.1] - 2026-08-10

### Changed

- Track Reed 0.5.1. Reed 0.5.0 added `POST /v1/search` — ranked evidence
  without generation, with its own rate limit and retrieval-thread budget —
  and fixed `reed backup restore` under the shipped compose by staging
  inside the target data directory; 0.5.1 tightens the data-directory
  permissions on bare-metal installs (the container was never affected).
- Drop the restore workaround the pre-0.5.0 Reed image made necessary:
  `scripts/restore.sh` no longer mounts a separate `/restore` volume with
  `REED_DATA_DIR` pointed inside it — the restore path is the simple form
  again, and the round-trip in CI proves it on every change.

### Security

- Justify the eight advisories the 2026-08-08 Trivy database refresh added
  across the Open WebUI and Qdrant images — each with the file's standing
  rationale: fixed upstream, no patched image to pin yet, loopback-only
  exposure, the weekly rescan and the next upstream release as the exit
  path. Reed's image keeps its zero-exception section.

## [0.1.0] - 2026-08-06

First public release: a local-first AI stack — general chat plus document Q&A with verifiable
citations — that comes up with one `docker compose up -d`, with every claim below verified in
CI on a clean runner on every change.

### Added

- The base stack: Ollama (in an excludable profile, with a documented BYO-Ollama mode for
  Apple Silicon), Qdrant, [Reed](https://github.com/Ulzuhan/reed) for document RAG with cited
  answers, and Open WebUI for general chat — one shared generation model
  (`qwen3.5:4b` by default) plus `embeddinggemma` for embeddings, pulled by a `model-init`
  service driven by `config/models.yaml`.
- Hardening by default: images pinned by digest, loopback-only ports, per-service container
  hardening, zero telemetry in every component, and a documented threat model in
  `docs/hardening.md`.
- Operations that are tested, not hoped for: a consistent backup pair (Reed archive + Qdrant
  snapshot) with a restore round-trip that runs in CI on every pull request, a preflight
  checker, and `docs/operations.md` covering upgrades, model changes and the Open WebUI
  PersistentConfig gotcha.
- A browser E2E suite (Playwright) that drives both UIs on every change: admin signup and
  chat, document upload → question → citation, and the permanent regression check that
  non-admin users get no upload door.
- Measured numbers with the platform declared per figure in `docs/benchmarking.md`: 36.3
  tokens/s with `qwen3.5:4b` on an Apple M5 (native Ollama), 19 s from `compose up` to a
  usable system in CI with models cached, ~2.9 GiB RAM for the whole stack — plus a rerunnable
  `benchmarks.yml` workflow and an honest 1/3/5-year cost comparison against cloud APIs.
- Deployment profiles: BYO-Ollama for the host's native inference, a GPU override (NVIDIA,
  `qwen3.5:9b`) validated syntactically in CI, and an air-gap profile —
  `scripts/package-offline.sh` builds a bundle with the pinned images, the model store, Reed's
  local model cache and every model's license terms; CI proves the full loop (package, wipe,
  install with container egress cut, smoke) on every change.
- The release pipeline itself: tags are validated against this changelog and the tip of main,
  the air-gap bundle is built with the full default model set, published as split release
  assets, and attested with `actions/attest-build-provenance`.
- Supply-chain posture: every action pinned by full SHA, Dependabot watching the compose
  image digests, the actions and the test tooling, gitleaks and Trivy on every PR plus a
  weekly rescan, and meta-tests that keep the workflows, the docs, the env example and the
  model catalog from drifting.

### Notes

- Model licenses: the Qwen3.5 models are Apache-2.0 (re-verified against the upstream model
  cards before this release); `embeddinggemma` ships under Google's Gemma Terms of Use with
  its Prohibited Use Policy — the air-gap bundle carries those terms because it redistributes
  the weights.
- The production override (TLS + auth in front of the UIs) is deliberately not in this
  release: it lands when it has its own CI validation. The roadmap in the README tracks it.

[Unreleased]: https://github.com/Ulzuhan/private-ai-stack/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Ulzuhan/private-ai-stack/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/Ulzuhan/private-ai-stack/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Ulzuhan/private-ai-stack/releases/tag/v0.1.0
