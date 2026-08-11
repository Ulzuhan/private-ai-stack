#!/usr/bin/env bash
# Install (or refresh) the "Reed Documents" pipe in Open WebUI — as code, not
# clicks in the admin panel. Idempotent: a second run refreshes the same
# function and exits 0. Requires the stack to be up:
#   docker compose up -d && ./scripts/install-reed-pipe.sh
# Auth, in order of preference:
#   WEBUI_ADMIN_API_KEY — an admin API key (Settings > Account), the
#     documented path; set it in your .env (never committed).
#   WEBUI_ADMIN_EMAIL + WEBUI_ADMIN_PASSWORD — sign in instead (used by CI,
#     where the first signup becomes the admin).
set -euo pipefail

cd "$(dirname "$0")/.."

WEBUI_URL=${WEBUI_URL:-http://127.0.0.1:3000}
REED_URL=${REED_URL:-http://127.0.0.1:8000}
FUNCTION_ID=reed_documents
PIPE_FILE=openwebui/reed_pipe.py

log() { printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*"; }
die() {
  echo "$*" >&2
  exit 1
}

# A variable's value: the real environment first, then the .env file. Never
# source .env wholesale — it may hold values the caller deliberately overrode.
env_or_dotenv() {
  local name=$1
  if [ -n "${!name:-}" ]; then
    printf '%s' "${!name}"
    return
  fi
  if [ -f .env ]; then
    grep -E "^${name}=" .env | tail -1 | cut -d= -f2- || true
  fi
}

[ -f "$PIPE_FILE" ] || die "${PIPE_FILE} not found — run this from anywhere inside the repo"

if ! curl -fsS "${REED_URL}/ready" >/dev/null 2>&1; then
  die "Reed is not ready at ${REED_URL} — is the stack up? (docker compose up -d)"
fi
if ! curl -fsS -o /dev/null "${WEBUI_URL}/"; then
  die "Open WebUI is not serving at ${WEBUI_URL} — is the stack up?"
fi

API_KEY=$(env_or_dotenv WEBUI_ADMIN_API_KEY)
if [ -n "$API_KEY" ]; then
  TOKEN=$API_KEY
else
  EMAIL=$(env_or_dotenv WEBUI_ADMIN_EMAIL)
  PASSWORD=$(env_or_dotenv WEBUI_ADMIN_PASSWORD)
  if [ -z "$EMAIL" ] || [ -z "$PASSWORD" ]; then
    die "No credentials: set WEBUI_ADMIN_API_KEY in .env (Open WebUI > Settings > Account > API keys), or pass WEBUI_ADMIN_EMAIL + WEBUI_ADMIN_PASSWORD."
  fi
  log "signing in as ${EMAIL}"
  TOKEN=$(curl -fsS -X POST "${WEBUI_URL}/api/v1/auths/signin" \
    -H 'content-type: application/json' \
    -d "$(jq -n --arg e "$EMAIL" --arg p "$PASSWORD" '{email: $e, password: $p}')" |
    jq -r .token)
  if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
    die "sign-in returned no token — check WEBUI_ADMIN_EMAIL / WEBUI_ADMIN_PASSWORD"
  fi
fi
AUTH="Authorization: Bearer ${TOKEN}"

# A valid token answers the session endpoint; this distinguishes "bad
# credentials" from the functions API's 401-when-missing quirk below.
if ! curl -fsS -o /dev/null -H "$AUTH" "${WEBUI_URL}/api/v1/auths/"; then
  die "Open WebUI rejected the credentials — regenerate the admin API key"
fi

code=$(curl -s -o /dev/null -w '%{http_code}' -H "$AUTH" \
  "${WEBUI_URL}/api/v1/functions/id/${FUNCTION_ID}")
# Upstream answers 401 (not 404) when the function does not exist; the token
# check above is what makes 401 unambiguous here.
if [ "$code" != "200" ] && [ "$code" != "401" ]; then
  die "unexpected HTTP ${code} looking up function ${FUNCTION_ID}"
fi

body=$(jq -n \
  --arg id "$FUNCTION_ID" \
  --arg name "Reed Documents" \
  --arg content "$(cat "$PIPE_FILE")" \
  --arg desc "Ask Reed's documents from the chat: calibrated answers with clickable citations, and an honest refusal when the evidence is not there." \
  '{id: $id, name: $name, content: $content, meta: {description: $desc, manifest: {}}}')

if [ "$code" = "200" ]; then
  curl -fsS -X POST -H "$AUTH" -H 'content-type: application/json' \
    -d "$body" "${WEBUI_URL}/api/v1/functions/id/${FUNCTION_ID}/update" >/dev/null
  log "updated function ${FUNCTION_ID}"
else
  curl -fsS -X POST -H "$AUTH" -H 'content-type: application/json' \
    -d "$body" "${WEBUI_URL}/api/v1/functions/create" >/dev/null
  log "created function ${FUNCTION_ID}"
fi

active=$(curl -fsS -H "$AUTH" "${WEBUI_URL}/api/v1/functions/id/${FUNCTION_ID}" |
  jq -r .is_active)
if [ "$active" != "true" ]; then
  curl -fsS -X POST -H "$AUTH" \
    "${WEBUI_URL}/api/v1/functions/id/${FUNCTION_ID}/toggle" >/dev/null
  log "activated function ${FUNCTION_ID}"
fi

# The valve mirrors the stack's own REED_API_KEY: one source of truth in .env.
REED_API_KEY_VALUE=$(env_or_dotenv REED_API_KEY)
valves=$(jq -n \
  --arg base "${REED_PIPE_BASE_URL:-http://reed:8000}" \
  --arg key "$REED_API_KEY_VALUE" \
  --arg ui "${REED_UI_URL:-http://127.0.0.1:8000}" \
  '{valves: {REED_BASE_URL: $base, REED_API_KEY: $key, REED_UI_URL: $ui}}')
curl -fsS -X POST -H "$AUTH" -H 'content-type: application/json' \
  -d "$valves" "${WEBUI_URL}/api/v1/functions/id/${FUNCTION_ID}/valves/update" >/dev/null
log "valves set (REED_BASE_URL, REED_API_KEY, REED_UI_URL)"

# The proof that matters: the pipe shows up as a selectable model.
if ! curl -fsS -H "$AUTH" "${WEBUI_URL}/api/v1/models" |
  jq -e --arg id "$FUNCTION_ID" '[.data[]?.id] | index($id)' >/dev/null; then
  die "installed, but ${FUNCTION_ID} does not appear in the model list"
fi
log "done — '${FUNCTION_ID}' is active and selectable as a model in the chat"
