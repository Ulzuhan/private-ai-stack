# Hardening and threat model

The stack's thesis is "private AI you can verify" — so its security posture
is written down, and the enforceable parts are enforced in CI.

## Zero telemetry, by default, per component

| Component | What is turned off | How |
|---|---|---|
| Qdrant | Usage telemetry | `QDRANT__TELEMETRY_DISABLED=true` |
| Open WebUI | Update checks, OpenAI API, Scarf analytics, anonymous telemetry | `OFFLINE_MODE=true`, `ENABLE_OPENAI_API=false`, `SCARF_NO_ANALYTICS=true`, `DO_NOT_TRACK=true`, `ANONYMIZED_TELEMETRY=false` |
| Reed | None exists to turn off | No telemetry in the project |
| Ollama | None beyond its local API | The stack adds no remote calls; model pulls are the only egress, once |

After the first `up` (which pulls models and, on first ever run, the images),
the stack needs no internet connection at all.

## Container hardening

Every service runs with `no-new-privileges`; Qdrant, Reed and model-init drop
**all** capabilities; Reed additionally runs with a read-only root filesystem
plus a small tmpfs for its upload spool, and `init: true`. Both UIs bind to
`127.0.0.1` only. Healthchecks and `unless-stopped` restarts are set
everywhere, so a crashed dependency comes back without intervention.

## Supply chain

- Every image is pinned by **tag and digest** — never `latest`.
- Dependabot (compose, GitHub Actions, and the test tooling) keeps pins from
  rotting.
- **Trivy** scans exactly the pinned image set on every PR, blocking on
  CRITICAL/HIGH; a weekly scheduled re-scan catches CVEs published between
  PRs. Findings without an available fix (base-image packages awaiting an
  upstream rebuild) are filtered by a written OPA policy in
  `.trivyignore.rego`, which can only shrink as fixes ship.
- **gitleaks** scans the full git history on every PR.
- All GitHub Actions are pinned by full SHA; a meta-test enforces it.
- Models are pulled from the Ollama registry at first start. Note the
  license asymmetry: `qwen3.5` is Apache-2.0 while `embeddinggemma` ships
  under Google's Gemma Terms of Use — relevant if you redistribute weights.

## Threat model (basic)

**Assets.** Your documents and their embeddings, your chat history, the
host machine, and (in regulated settings) your compliance story.

**In scope and addressed.**

- *Malicious document content* — Reed parses uploads in an isolated process
  with rlimits and strips hidden text (HTML comments, invisible spans,
  DOCX tricks) that could smuggle instructions into the context.
- *Accidental exposure* — loopback-only ports; Qdrant and Ollama are not
  published at all; Reed requires an API key before its API leaves localhost
  (see [operations.md](operations.md#exposing-the-stack-beyond-localhost)).
- *Container escape / lateral movement* — read-only rootfs, dropped
  capabilities, no-new-privileges, minimal tmpfs.
- *Dependency and base-image CVEs* — pinned digests, per-PR and weekly
  scanning, automated bump PRs.
- *Silent config drift* — `ENABLE_PERSISTENT_CONFIG=false` keeps Open WebUI's
  security-relevant flags under version control; meta-tests fail CI if docs
  or `.env.example` drift from the compose files.

**Out of scope (be honest with yourself).**

- *Anyone with shell access to the host* owns the data — full-disk
  encryption and OS hygiene are your layer.
- *The quickstart has no TLS and no SSO* — it is a localhost setup. The
  production override (Caddy TLS + basic auth) is the roadmap item for
  shared deployments.
- *Model behavior* — a 4B local model hallucinates more than a frontier
  cloud model. Reed mitigates this for documents with evidence thresholds
  and refusals; general chat has no such guardrail. Choose your model with
  your risk in mind.
- *Availability* — this is a single-node stack with backups, not HA.

## What the stack deliberately does NOT do

No telemetry, no cloud fallback, no anonymous usage pings, no automatic
updates of anything at runtime (updates are PRs you review), no exposed
metrics endpoints, no hidden admin backdoor: Open WebUI's first-visitor
signup creates a local account on your machine, and Reed has no accounts at
all behind its API key.
