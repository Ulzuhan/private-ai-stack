# Benchmarking

Numbers without a platform are marketing. Every figure published for this
stack declares where it was measured, on what hardware, with which model —
and the CI-derived ones are reproducible by anyone who forks the repo.

## What is measured, and where

### On the author's Mac (native Ollama, BYO mode — Metal)

| Metric | Model | Value | Platform |
|---|---|---|---|
| Tokens/s, generation | `qwen3.5:4b` | *not yet measured* | Apple Silicon, native Ollama |
| Time to first token, cold / warm | `qwen3.5:4b` | *not yet measured* | Apple Silicon, native Ollama |

### In CI (GitHub `ubuntu-latest`, 4 vCPU, no GPU — full containerized stack)

| Metric | Value | Platform |
|---|---|---|
| `compose up` to usable system, models cached | *not yet measured* | CI runner |
| `compose up` to usable system, cold model pull | *not yet measured* | CI runner |
| RAM per service (`docker stats` after the smoke) | *not yet measured* | CI runner |

The metrics milestone ahead of v0.1.0 fills these tables and adds a
`workflow_dispatch` job so any fork can reproduce the CI numbers on its own
runner — "works on my machine" raised to "works on yours, and here is the
receipt".

### Referenced, not re-measured

- **RAG quality**: Reed's published evaluation against its golden set of 41
  questions — same model pair (`qwen3.5:4b` + `embeddinggemma`) and the same
  retrieval configuration this stack ships. See
  [Reed](https://github.com/Ulzuhan/reed). Re-running it in CI with the tiny
  `qwen3.5:0.8b` smoke model would produce meaningless numbers, so the stack
  links the measurement instead of faking one.
- **Cost comparison**: local stack vs cloud API over 1/3/5 years, framed
  honestly — "for workloads where a 4B–9B model is enough", with the
  assumptions spelled out here when the table lands.

### Awaiting community hardware

- **GPU profile** (`qwen3.5:9b`): no NVIDIA hardware is available to the
  author. Its cells will be marked *not yet measured — contributions
  welcome*, with an issue to collect them.

## Method notes

- CI timing numbers come from the runner's own timestamps and
  `docker stats --no-stream`; variance across runners is real and will be
  reported as a range once there are enough samples.
- The tiny CI model (`qwen3.5:0.8b`) proves the circuit on every PR; it is
  never used for quality or throughput claims.
