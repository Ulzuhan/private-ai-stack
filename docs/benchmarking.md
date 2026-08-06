# Benchmarking

Numbers without a platform are marketing. Every figure published for this
stack declares where it was measured, on what hardware, with which model —
and the CI-derived ones are reproducible by anyone who forks the repo.

## What is measured, and where

### On the author's Mac (native Ollama, BYO mode — Metal)

Measured 2026-08-06 with `scripts/benchmark-local.py` against a native
Ollama 0.32.5, models already on disk. Apple M5, 32 GB unified memory.

| Metric | Model | Value | Platform |
|---|---|---|---|
| Tokens/s, generation (warm) | `qwen3.5:4b` | 36.3 | Apple M5, native Ollama |
| Time to first token, cold (model load included) | `qwen3.5:4b` | 1.93 s | Apple M5, native Ollama |
| Time to first token, warm | `qwen3.5:4b` | 0.22 s | Apple M5, native Ollama |
| Embedding latency | `embeddinggemma` | 53 ms | Apple M5, native Ollama |

### In CI (GitHub `ubuntu-latest`, 4 vCPU AMD EPYC, 16 GB, no GPU — full containerized stack)

Measured 2026-08-06 by the `benchmarks.yml` workflow on a fresh runner,
with the tiny `qwen3.5:0.8b` smoke model (it proves the circuit; absolute
inference speed on a shared CPU runner is not the claim here).

| Metric | Value | Platform |
|---|---|---|
| `compose up` to usable system, cold model pull | 95 s | CI runner |
| Smoke test passed (LLM answers, Reed cites) | 105 s | CI runner |
| `compose up` to usable system, models cached on disk | 19 s | CI runner |
| RAM per service (`docker stats` after the smoke) | 2.9 GiB total — breakdown below | CI runner |

RAM per service, right after the smoke test:

| Service | Memory |
|---|---|
| ollama (0.8b model loaded) | 2.01 GiB |
| open-webui | 688 MiB |
| reed | 160 MiB |
| qdrant | 96 MiB |

Reproduce these numbers on your own fork: **Actions → Benchmarks → Run
workflow**. The report lands in the run summary and as a downloadable
artifact; "works on my machine" raised to "works on yours, and here is the
receipt".

### Referenced, not re-measured

- **RAG quality**: Reed's published evaluation against its golden set of 41
  questions — same model pair (`qwen3.5:4b` + `embeddinggemma`) and the same
  retrieval configuration this stack ships. See
  [Reed](https://github.com/Ulzuhan/reed). Re-running it in CI with the tiny
  `qwen3.5:0.8b` smoke model would produce meaningless numbers, so the stack
  links the measurement instead of faking one.

## Cost: local vs cloud API, honestly framed

The question is only meaningful for workloads where a 4B–9B local model is
good enough — personal document Q&A, summarization, drafting. If you need
frontier-model quality, this comparison does not apply and privacy is the
only reason to stay local.

Assumptions, spelled out so you can substitute your own:

- **Workload**: ~2.5 M tokens/month combined (a few dozen RAG questions a
  day, retrieved context included).
- **Cloud prices are illustrative points, not quotes** — plug in your
  provider's current rates: a budget tier at $0.15/M input + $0.60/M
  output; a frontier tier at $3/M input + $15/M output.
- **Local hardware**: two scenarios — the machine you already own (sunk
  cost, only electricity counts) and a machine bought for this purpose
  ($800 amortized over 5 years).
- **Electricity**: ~19 h of generation/month at 36 tok/s on the M5, ~40 W
  average draw while generating, $0.20/kWh → well under $2/year. Standby
  is excluded; the machine is not inference-only.

| Scenario | 1 year | 3 years | 5 years |
|---|---|---|---|
| Cloud, budget tier | ~$7 | ~$22 | ~$36 |
| Cloud, frontier tier | ~$162 | ~$486 | ~$810 |
| Local, hardware already owned | ~$2 | ~$6 | ~$10 |
| Local, $800 machine bought for this | ~$162 | ~$486 | ~$810 |

Read it honestly: at this volume a **budget** cloud API is nearly free, and
a dedicated machine never pays for itself on electricity alone. The local
stack wins on **privacy, sovereignty and zero marginal cost at any volume**
— and against the frontier tier it breaks even inside the first year even
counting the hardware. The inflection point is not price per token; it is
whether your documents are allowed to leave the machine at all.

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
- `scripts/benchmark-local.py` measures any host with a native Ollama:
  cold/warm TTFT, warm throughput and embedding latency, and prints
  Markdown rows ready to paste into the table above.
