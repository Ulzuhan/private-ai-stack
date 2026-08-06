#!/usr/bin/env bash
# package-offline.sh — build the air-gap transfer bundle on a machine WITH
# internet access. The bundle carries everything the isolated machine needs:
# the pinned images, the Ollama model store, the compose files, the model
# licenses (mandatory: the bundle redistributes weights) and an installer.
#
#   ./scripts/package-offline.sh [output-dir]
#
# Package the GPU model set instead of the default one:
#   GENERATION_MODEL=qwen3.5:9b ./scripts/package-offline.sh
#
# See docs/air-gap.md for the full procedure, including how CI validates it.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUT=${1:-"${ROOT}/dist"}
GENERATION_MODEL=${GENERATION_MODEL:-qwen3.5:4b}
EMBEDDING_MODEL=${EMBEDDING_MODEL:-embeddinggemma}
BUNDLE=private-ai-stack-offline
# Packaging uses its own compose project so it never touches the volumes of a
# deployment that happens to live on the connected machine.
PACK_PROJECT=private-ai-stack-pack
# Project name the ISOLATED side will run as — the `name:` of the base
# compose file, so the bundle lands exactly where a normal install would.
TARGET_PROJECT=private-ai-stack

log() { printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*"; }
die() {
  echo "error: $*" >&2
  exit 1
}

hash_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$@"
  else
    shasum -a 256 "$@"
  fi
}

compose() {
  docker compose --project-directory "$ROOT" -p "$PACK_PROJECT" \
    -f "$ROOT/docker-compose.yml" "$@"
}

# model_field <model> <field> — read one scalar from config/models.yaml.
# The catalog's layout is fixed and asserted by the meta-tests, so this
# indentation-aware awk is a reader, not a parser.
model_field() {
  awk -v key="  $1:" -v field="    $2:" '
    index($0, key) == 1 { hit = 1; next }
    hit && index($0, field) == 1 {
      sub(field, ""); gsub(/^ +| +$/, ""); print; exit
    }
    hit && /^  [^ ]/ { exit }
  ' "$ROOT/config/models.yaml"
}

command -v docker >/dev/null 2>&1 || die "docker is required"
docker info >/dev/null 2>&1 || die "the docker daemon is not running"
[ -f "$ROOT/config/models.yaml" ] || die "config/models.yaml not found — run from a full checkout"

bundle_dir="${OUT}/${BUNDLE}"
rm -rf "$bundle_dir"
mkdir -p "$bundle_dir/licenses" "$bundle_dir/compose" "$bundle_dir/scripts"
# docker -v treats a relative path as a named volume; the bundle dir must be
# absolute before any bind mount uses it.
bundle_dir=$(cd "$bundle_dir" && pwd)
OUT=$(dirname "$bundle_dir")

# --- images ------------------------------------------------------------------

log "pulling the pinned images"
compose pull

images=()
while IFS= read -r line; do images+=("$line"); done < <(compose config --images | sort -u)
[ "${#images[@]}" -gt 0 ] || die "no images resolved from the compose file"

ollama_image=""
for image in "${images[@]}"; do
  case "$image" in
  ollama/ollama:*) ollama_image=$image ;;
  esac
done
[ -n "$ollama_image" ] || die "no ollama image found in the compose file"

log "saving ${#images[@]} images (this takes a few minutes)"
docker save "${images[@]}" | gzip >"$bundle_dir/images.tar.gz"

# --- models ------------------------------------------------------------------

log "pulling the models through a throwaway stack project"
compose up -d ollama
deadline=$((SECONDS + 300))
until [ "$(docker inspect -f '{{.State.Health.Status}}' "${PACK_PROJECT}-ollama-1" 2>/dev/null || true)" = "healthy" ]; do
  if ((SECONDS >= deadline)); then
    compose down
    die "the packaging ollama never became healthy"
  fi
  sleep 3
done
compose exec -T ollama ollama pull "$GENERATION_MODEL"
compose exec -T ollama ollama pull "$EMBEDDING_MODEL"
compose down

log "exporting the model store"
# The image's entrypoint is the ollama CLI itself; override it to reach tar.
docker run --rm --entrypoint tar \
  -v "${PACK_PROJECT}_ollama_models:/models:ro" \
  -v "$bundle_dir:/out" \
  "$ollama_image" czf /out/models.tar.gz -C /models .
docker volume rm "${PACK_PROJECT}_ollama_models" >/dev/null

# --- licenses (mandatory: the bundle redistributes model weights) ------------

for model in "$GENERATION_MODEL" "$EMBEDDING_MODEL"; do
  license=$(model_field "$model" license)
  url=$(model_field "$model" license_url)
  if [ -z "$license" ] || [ -z "$url" ]; then
    die "config/models.yaml has no license entry for ${model} — add one before packaging"
  fi
  safe=$(printf '%s' "$model" | tr ':/' '--')
  if [ "$license" = "Apache-2.0" ]; then
    cp "$ROOT/LICENSE" "$bundle_dir/licenses/${safe}-LICENSE.txt"
    log "license for ${model}: Apache-2.0 (bundled from LICENSE)"
  else
    curl -fsSL "$url" -o "$bundle_dir/licenses/${safe}-terms.html" ||
      die "could not fetch the terms for ${model} from ${url} — the bundle may not ship without them"
    log "license for ${model}: ${license} (fetched from ${url})"
  fi
done
cat >"$bundle_dir/licenses/README.txt" <<'EOF'
The models in this bundle are redistributed under the terms recorded in
config/models.yaml and included here per model. Note that embeddinggemma is
NOT open source: Google's Gemma Terms of Use and its Prohibited Use Policy
apply. Read each file before deploying the bundle.
EOF

# --- stack files, manifest, installer ----------------------------------------

cp "$ROOT/docker-compose.yml" "$ROOT/docker-compose.airgap.yml" "$bundle_dir/compose/"
cp "$ROOT/.env.example" "$bundle_dir/compose/.env.example"
cp "$ROOT/scripts/smoke-test.sh" "$ROOT/scripts/airgap-install.sh" "$bundle_dir/scripts/"
cp "$ROOT/config/models.yaml" "$bundle_dir/models.yaml"

cat >"$bundle_dir/manifest.env" <<EOF
# Generated by package-offline.sh — consumed by scripts/airgap-install.sh.
TARGET_PROJECT=${TARGET_PROJECT}
OLLAMA_IMAGE=${ollama_image}
GENERATION_MODEL=${GENERATION_MODEL}
EMBEDDING_MODEL=${EMBEDDING_MODEL}
EOF

{
  echo "private-ai-stack offline bundle"
  echo "created: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "generation model: ${GENERATION_MODEL}"
  echo "embedding model: ${EMBEDDING_MODEL}"
  echo "images:"
  printf '  %s\n' "${images[@]}"
  echo
  (cd "$bundle_dir" && hash_file images.tar.gz models.tar.gz)
} >"$bundle_dir/MANIFEST.txt"

mv "$bundle_dir/scripts/airgap-install.sh" "$bundle_dir/install.sh"

tar czf "${OUT}/${BUNDLE}.tar.gz" -C "$OUT" "$BUNDLE"
hash_file "${OUT}/${BUNDLE}.tar.gz" | tee "${OUT}/${BUNDLE}.tar.gz.sha256"

log "bundle ready: ${OUT}/${BUNDLE}.tar.gz"
log "transfer it together with its .sha256 — on the isolated machine:"
log "  tar xzf ${BUNDLE}.tar.gz && cd ${BUNDLE} && ./install.sh"
