# Air-gap deployment

The stack can run on a machine with **no internet access at all**. A bundle
built on a connected machine carries everything the isolated one needs:
the pinned images, the Ollama model store, Reed's local model cache (its
FastEmbed reranker — the isolated side has no HuggingFace), the compose
files, the model licenses and an installer. On the isolated side the
stack's bridge network runs with **masquerading disabled** — containers
talk to each other and serve their loopback ports to the host, but their
packets have no route outward — and every service runs with
`pull_policy: never`, so no container ever reaches for a registry. (An
`internal: true` network would cut egress too, but it also kills the
published loopback ports — and then the UIs are unreachable from the very
machine they run on.)

This page is the procedure. The **How this is validated** section at the
bottom declares how CI proves it on every change.

## What you need

- **Connected machine**: docker with compose v2.30+, ~20 GB free disk, this
  repository checked out.
- **Isolated machine**: docker with compose v2.30+, ~20 GB free disk,
  nothing else. The smoke test additionally wants `jq`, but it is optional.
- A transfer medium both machines trust (USB drive, SCP over a one-way
  link, whatever your policy allows).

## 1. Build the bundle (connected machine)

```bash
./scripts/package-offline.sh            # writes dist/
```

To package the GPU model set instead of the default one:

```bash
GENERATION_MODEL=qwen3.5:9b ./scripts/package-offline.sh
```

The script pulls the pinned images, pulls the models through a throwaway
compose project (it never touches the volumes of a deployment living on
that machine — but stop any running deployment first: the packaging stack
briefly binds the same loopback ports), warms Reed's bootstrap so its local
model cache (the FastEmbed reranker) travels too, fetches the license terms
of every packaged model — the bundle **redistributes model weights**, so
the terms are mandatory, not decorative — and writes:

```
dist/private-ai-stack-offline.tar.gz
dist/private-ai-stack-offline.tar.gz.sha256
```

Note on licenses: `embeddinggemma` is **not** open source — Google's Gemma
Terms of Use and its Prohibited Use Policy apply, and the bundle includes
them. The Qwen3.5 models are recorded as Apache-2.0 in
[`config/models.yaml`](../config/models.yaml). Read `licenses/README.txt`
inside the bundle before deploying it.

## 2. Transfer and verify

Copy the tarball and its `.sha256` to the isolated machine, then:

```bash
sha256sum -c private-ai-stack-offline.tar.gz.sha256
```

If the checksum does not match, do not install — re-transfer.

## 3. Install (isolated machine)

```bash
tar xzf private-ai-stack-offline.tar.gz
cd private-ai-stack-offline
./install.sh
```

The installer verifies the bundle's internal checksums, loads the images,
checks that every image the compose files name is actually present,
restores the model store into the same named volume a normal install would
use, pins the packaged model selection into `compose/.env`, and starts the
stack with the air-gap override (`docker-compose.airgap.yml`): no NAT off
the bridge, no pulls. In this mode `model-init` does not download anything —
it **verifies** that every model the configuration expects is already in
the store, and fails loudly if one is missing.

One honest wrinkle: `docker save`/`load` drops digest metadata, so the
bundle's compose copy pins images by tag and `MANIFEST.txt` records the
full `name:tag@sha256:…` references it was built from. The tarball's SHA-256
plus the per-file checksums tie those tags to the exact packaged bits.

When it finishes:

- **Chat**: <http://127.0.0.1:3000>
- **Documents (Reed)**: <http://127.0.0.1:8000>

Optional but recommended, if `jq` is available on the isolated machine:

```bash
(cd compose && COMPOSE_FILE=docker-compose.yml:docker-compose.airgap.yml \
  ../scripts/smoke-test.sh)
```

## Operating air-gapped

- **Backups and restores work unchanged** — they are local operations. See
  [operations.md](operations.md).
- **Updates are re-packaging**: build a new bundle on the connected machine
  when the pins move, transfer, install over the top. Volumes persist, so
  documents and the vector store survive.
- **Model changes are re-packaging too**: pull the new model into a bundle
  (`GENERATION_MODEL`/`EMBEDDING_MODEL` at package time) and install it.

## How this is validated

The `airgap` job in CI runs the full loop on every change, with the tiny
CI model set (`qwen3.5:0.8b` + `embeddinggemma`) because the full models do
not fit a runner:

1. `package-offline.sh` builds the real bundle, licenses included.
2. `docker system prune -af --volumes` wipes **every** local image and
   volume — the simulation of the isolated machine. If the bundle forgot
   anything, nothing is left to paper over it.
3. `install.sh` runs from the extracted tarball.
4. The stack comes up with masquerading disabled on its bridge — the
   runner's own egress stops being usable by the containers, while the
   loopback-published UIs keep working.
5. The same smoke test as the online CI passes: models verified, Reed
   ingests a document and answers with a citation, both UIs serve.

The mechanism is identical to the full-size package; only the model sizes
differ. That is the honest limit of the validation, and it is stated here
rather than implied away.
