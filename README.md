# private-ai-stack

**A production-minded local AI stack — general chat plus document Q&A with
verifiable citations — in one `docker compose up -d`.** Nothing leaves your
machine: no cloud APIs, no telemetry, models run on your own hardware.

> 🚧 **Work in progress, building toward v0.1.0.** Everything merged here works
> and is verified in CI on a clean runner — but the full case study
> (architecture deep-dive, hardening guide, air-gap packaging, benchmarks) is
> still landing. Watch the repo or check the issues for the roadmap.

## What's inside

| Service | Pinned image | Role |
|---|---|---|
| [Ollama](https://ollama.com) | `ollama/ollama:0.32.5` | Local inference, shared by the whole stack |
| [Qdrant](https://qdrant.tech) | `qdrant/qdrant:v1.18.3` | Vector store behind the RAG service |
| [Open WebUI](https://github.com/open-webui/open-webui) | `open-webui:v0.11.0` | General chat UI |
| [Reed](https://github.com/Ulzuhan/reed) | `reed:0.4.0` | Document RAG with citations, hybrid retrieval and its own UI |

Every image is pinned by tag **and digest**. Containers run hardened
(`read_only`, `cap_drop: ALL`, `no-new-privileges` where the service allows
it), telemetry is off by default everywhere, and all ports bind to
`127.0.0.1` only.

## Quickstart

```bash
docker compose up -d
```

That single command is the whole setup: a one-shot `model-init` service pulls
the models (~4 GB) on first start. Follow it with
`docker compose logs -f model-init`.

Then open:

- **Chat** — Open WebUI at <http://127.0.0.1:3000>. The first visit creates
  the admin account, locally.
- **Your documents** — Reed at <http://127.0.0.1:8000>. Upload a PDF,
  Markdown, DOCX or text file and ask; answers stream with clickable
  citations.

**Two doors, one rule:** Open WebUI is for general chat, Reed is for your
documents. File upload inside Open WebUI is disabled on purpose so documents
always go through the RAG pipeline — retrieval you can inspect, citations you
can click, refusals when the documents don't answer.

### On a Mac? Bring your own Ollama

Docker on macOS has no Metal passthrough, so the containerized Ollama runs
CPU-only. The fast path is a [native Ollama](https://ollama.com/download)
on the host:

```bash
ollama pull qwen3.5:4b && ollama pull embeddinggemma
docker compose -f docker-compose.yml -f docker-compose.byo.yml up -d
```

## Requirements

- Docker with Compose v2.30+
- 8 GB RAM minimum (16 GB comfortable) for the default `qwen3.5:4b` +
  `embeddinggemma` pair
- ~15–20 GB free disk for images and models

## Configuration

Everything is tunable through environment variables — see
[`.env.example`](.env.example) for the documented set. The stack runs with no
`.env` file at all.

## Verified, not promised

CI brings the full stack up on a clean GitHub runner on every change: models
pull, the LLM answers, Reed ingests a document and returns a cited answer,
both UIs serve. If the badge is green, the quickstart works.

## License

[Apache-2.0](LICENSE).

---

*Built by José M. Cotarelo — at [Hesperia Labs](https://hesperialabs.com) we
deploy and operate stacks like this on-premises for regulated industries.*

*Documentación en español: [README.es.md](README.es.md).*
