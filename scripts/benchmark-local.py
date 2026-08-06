#!/usr/bin/env python3
"""Measure local inference numbers for docs/benchmarking.md — native Ollama.

This is the BYO half of the stack's benchmarks: it talks to a *native*
Ollama on the host (Metal on Apple Silicon), never to a container. It
measures, for a fixed prompt and a fixed generation budget:

- TTFT cold: seconds to the first token with the model fully unloaded
  (includes model load).
- TTFT warm: seconds to the first token with the model already resident.
- Generation throughput: eval_count / eval_duration, as reported by the
  Ollama API (tokens/s), warm.
- Embedding latency for the stack's embedding model.

Usage: python3 scripts/benchmark-local.py [--model qwen3.5:4b]
Prints a Markdown table ready to paste into docs/benchmarking.md, plus the
raw JSON on stderr for the record. Stdlib only — no dependencies.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:11434"
PROMPT = (
    "Explain in one paragraph why the sky appears blue on a clear day, "
    "addressing someone with no physics background."
)
NUM_PREDICT = 128
WARM_RUNS = 3
EMBED_TEXT = "Expenses above 75 euros require pre-approval by a line manager."


def _post(path: str, payload: dict, *, stream: bool = False):
    request = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    return urllib.request.urlopen(request, timeout=600)


def _unload(model: str) -> None:
    # keep_alive=0 with no prompt makes Ollama drop the model from memory.
    _post("/api/generate", {"model": model, "keep_alive": 0}).read()


def _generate_timed(model: str) -> dict:
    payload = {
        "model": model,
        "prompt": PROMPT,
        "stream": True,
        "options": {"num_predict": NUM_PREDICT, "temperature": 0},
    }
    start = time.monotonic()
    ttft = None
    final = {}
    with _post("/api/generate", payload) as response:
        for line in response:
            chunk = json.loads(line)
            # Thinking models (qwen3.5) stream reasoning in `thinking` and
            # leave `response` empty until they answer — either field counts
            # as a produced token.
            if ttft is None and (chunk.get("response") or chunk.get("thinking")):
                ttft = time.monotonic() - start
            if chunk.get("done"):
                final = chunk
    total = time.monotonic() - start
    tokens_per_second = final["eval_count"] / (final["eval_duration"] / 1e9)
    return {
        "ttft_s": round(ttft, 2),
        "total_s": round(total, 2),
        "eval_tokens": final["eval_count"],
        "tokens_per_second": round(tokens_per_second, 1),
        "load_s": round(final["load_duration"] / 1e9, 2),
    }


def _embed_timed(model: str) -> float:
    payload = {"model": model, "prompt": EMBED_TEXT}
    start = time.monotonic()
    _post("/api/embed", payload).read()
    return time.monotonic() - start


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3.5:4b")
    parser.add_argument("--embed-model", default="embeddinggemma")
    args = parser.parse_args()

    machine = {
        "cpu": subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True, text=True, check=True,
        ).stdout.strip(),
        "ram_gb": round(
            int(subprocess.run(
                ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True,
                check=True,
            ).stdout) / 2**30
        ),
        "os": f"{platform.system()} {platform.release()}",
        "ollama": json.loads(urllib.request.urlopen(f"{BASE}/api/version", timeout=5).read())[
            "version"
        ],
    }

    _unload(args.model)
    time.sleep(2)
    cold = _generate_timed(args.model)
    warm = [_generate_timed(args.model) for _ in range(WARM_RUNS)]
    warm_ttft = min(run["ttft_s"] for run in warm)
    warm_tps = max(run["tokens_per_second"] for run in warm)
    embed_s = min(_embed_timed(args.embed_model) for _ in range(WARM_RUNS))

    report = {
        "platform": machine,
        "model": args.model,
        "embed_model": args.embed_model,
        "prompt": PROMPT,
        "num_predict": NUM_PREDICT,
        "cold": cold,
        "warm_runs": warm,
        "embed_latency_s": round(embed_s, 3),
    }
    print(json.dumps(report, indent=2), file=sys.stderr)

    where = f"{machine['cpu']}, {machine['ram_gb']} GB, native Ollama {machine['ollama']} (Metal)"
    print(f"| TTFT, cold (incl. model load) | `{args.model}` | {cold['ttft_s']} s | {where} |")
    print(f"| TTFT, warm | `{args.model}` | {warm_ttft} s | {where} |")
    print(f"| Generation throughput, warm | `{args.model}` | {warm_tps} tok/s | {where} |")
    print(f"| Embedding latency (1 doc excerpt) | `{args.embed_model}` | {embed_s * 1000:.0f} ms | {where} |")


if __name__ == "__main__":
    main()
