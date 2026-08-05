#!/usr/bin/env bash
# Curl-level smoke test: the models arrive, Reed ingests a document and answers
# with a citation, and both UIs serve. Requires the stack to be up:
#   docker compose up -d && ./scripts/smoke-test.sh
# Honors COMPOSE_FILE, so CI can point it at its override.
set -euo pipefail

REED_URL=${REED_URL:-http://127.0.0.1:8000}
WEBUI_URL=${WEBUI_URL:-http://127.0.0.1:3000}
READY_TIMEOUT_SECONDS=${READY_TIMEOUT_SECONDS:-600}

log() { printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*"; }

log "waiting for model-init to finish pulling models"
docker compose wait model-init

log "waiting for reed to become ready"
deadline=$((SECONDS + READY_TIMEOUT_SECONDS))
until curl -fsS "${REED_URL}/ready" > /dev/null 2>&1; do
  if ((SECONDS >= deadline)); then
    echo "reed never became ready within ${READY_TIMEOUT_SECONDS}s" >&2
    exit 1
  fi
  sleep 3
done

log "checking that open-webui serves"
code=$(curl -s -o /dev/null -w '%{http_code}' "${WEBUI_URL}/")
if [ "$code" != "200" ]; then
  echo "open-webui returned HTTP ${code}" >&2
  exit 1
fi

log "uploading a sample document to reed"
tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
printf '# Expenses policy\n\nExpenses above 75 euros require pre-approval.\n' \
  > "${tmpdir}/expenses.md"
document_id=$(curl -sf -F "file=@${tmpdir}/expenses.md" \
  "${REED_URL}/v1/documents" | jq -r .document_id)
log "uploaded ${document_id}"

log "waiting for ingestion"
status=pending
for _ in $(seq 90); do
  status=$(curl -sf "${REED_URL}/v1/documents/${document_id}" | jq -r .status)
  [ "$status" = "ready" ] && break
  if [ "$status" = "error" ]; then
    curl -s "${REED_URL}/v1/documents/${document_id}" >&2
    exit 1
  fi
  sleep 2
done
if [ "$status" != "ready" ]; then
  echo "ingestion never finished (last status: ${status})" >&2
  exit 1
fi

log "asking a question — the answer must come from the document"
answer=$(curl -sf -X POST "${REED_URL}/v1/ask" \
  -H 'content-type: application/json' \
  -d '{"question":"What is the expense pre-approval threshold?","stream":false}')
echo "$answer" | jq .
echo "$answer" | jq -e '.sources | length > 0' > /dev/null
echo "$answer" | jq -e \
  '(.answer | contains("[1]")) or (.citation_status == "valid")' > /dev/null

log "smoke test passed"
