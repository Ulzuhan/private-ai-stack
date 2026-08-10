# Changelog

All notable changes to private-ai-stack are documented here. The project follows Semantic
Versioning while it is pre-1.0: minor releases may change operational behavior, and patch
releases contain compatible fixes.

## [Unreleased]

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

[Unreleased]: https://github.com/Ulzuhan/private-ai-stack/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/Ulzuhan/private-ai-stack/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Ulzuhan/private-ai-stack/releases/tag/v0.1.0
