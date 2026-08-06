#!/usr/bin/env bash
# airgap-install.sh — install the offline bundle on the isolated machine.
# Packaged as install.sh at the bundle root by package-offline.sh; all
# package-time choices (image refs, models, project name) come from
# manifest.env next to it. Requires docker with compose v2 and enough disk;
# needs no network at all.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

log() { printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*"; }
die() {
  echo "error: $*" >&2
  exit 1
}

[ -f manifest.env ] || die "manifest.env not found — run from the bundle root"
# shellcheck source=/dev/null
. ./manifest.env
: "${TARGET_PROJECT:?}" "${OLLAMA_IMAGE:?}" "${GENERATION_MODEL:?}" "${EMBEDDING_MODEL:?}"

command -v docker >/dev/null 2>&1 || die "docker is required"
docker info >/dev/null 2>&1 || die "the docker daemon is not running"

if command -v sha256sum >/dev/null 2>&1; then
  grep '\.tar\.gz' MANIFEST.txt | sha256sum -c - ||
    die "checksum mismatch — re-transfer the bundle"
fi

log "loading the pinned images"
docker load -i images.tar.gz

log "verifying every bundled image is present"
missing=0
while IFS= read -r image; do
  if ! docker image inspect "$image" >/dev/null 2>&1; then
    echo "missing after load: $image" >&2
    missing=1
  fi
done < <(docker compose --project-directory compose \
  -f compose/docker-compose.yml -f compose/docker-compose.airgap.yml config --images)
[ "$missing" -eq 0 ] || die "the image load was incomplete — re-transfer the bundle"

log "restoring the model store"
docker volume create "${TARGET_PROJECT}_ollama_models" >/dev/null
# The image's entrypoint is the ollama CLI itself; override it to reach tar.
docker run --rm --entrypoint tar \
  -v "${TARGET_PROJECT}_ollama_models:/models" \
  -v "$PWD:/pkg:ro" \
  "$OLLAMA_IMAGE" xzf /pkg/models.tar.gz -C /models

# Reed's volume pairs its local model cache with the document registry. An
# existing volume means an existing deployment — never clobber its registry.
if docker volume inspect "${TARGET_PROJECT}_reed_data" >/dev/null 2>&1; then
  log "reed data volume already exists — keeping it (its cache is local too)"
else
  log "restoring reed's local model cache"
  docker volume create "${TARGET_PROJECT}_reed_data" >/dev/null
  docker run --rm --entrypoint tar \
    -v "${TARGET_PROJECT}_reed_data:/data" \
    -v "$PWD:/pkg:ro" \
    "$OLLAMA_IMAGE" xzf /pkg/reed-data.tar.gz -C /data
fi

log "pinning the packaged model selection"
cat >compose/.env <<EOF
GENERATION_MODEL=${GENERATION_MODEL}
EMBEDDING_MODEL=${EMBEDDING_MODEL}
EOF

log "starting the stack (no NAT off the bridge, no egress)"
docker compose --project-directory compose \
  -f compose/docker-compose.yml -f compose/docker-compose.airgap.yml up -d

log "done — chat at http://127.0.0.1:3000, documents at http://127.0.0.1:8000"
echo "Smoke test, if jq is available on this machine:"
echo "  (cd compose && COMPOSE_FILE=docker-compose.yml:docker-compose.airgap.yml ../scripts/smoke-test.sh)"
