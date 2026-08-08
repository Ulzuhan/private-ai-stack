#!/usr/bin/env bash
# Restore a backup pair created by backup.sh: Reed's archive first, then the
# Qdrant snapshot, with Reed stopped the whole time so the two halves come
# back as one consistent state.
#
#   ./scripts/restore.sh backups/<label>
#
# Reed's restore refuses a non-empty data directory, so the supported flow is
# a wiped stack (`docker compose down -v && docker compose up -d`) followed by
# this script — it clears whatever the fresh start created before restoring.
#
# Robust alternative when the Qdrant half is missing or suspect: restore only
# the Reed archive, then rebuild the vectors from the stored originals with
#   docker compose run --rm --no-deps reed reed index reindex
# (slower — it re-embeds everything — but consistency is guaranteed).
set -euo pipefail

COLLECTION=${REED_COLLECTION:-reed_chunks}
REED_URL=${REED_URL:-http://127.0.0.1:${REED_PORT:-8000}}
READY_TIMEOUT_SECONDS=${READY_TIMEOUT_SECONDS:-300}

dir=${1:?usage: restore.sh <backup-directory>}
archive="${dir}/reed-backup.tar.gz"
snapshot="${dir}/qdrant.snapshot"

log() { printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*"; }

for file in "$archive" "$snapshot" "${dir}/manifest.json"; do
  if [ ! -f "$file" ]; then
    echo "not a backup directory: missing ${file}" >&2
    exit 1
  fi
done

log "stopping reed"
docker compose stop reed
trap 'docker compose start reed > /dev/null' EXIT

log "clearing reed data volume"
docker compose run --rm --no-deps -T \
  reed sh -c 'find /data -mindepth 1 -delete'

log "restoring reed archive from ${archive}"
# Reed 0.5.0 stages the restore inside REED_DATA_DIR itself, so the service's
# own /data mount is all this needs. Earlier versions staged beside it, which
# on a read-only rootfs meant staging on / — hence the second mount and the
# REED_DATA_DIR override this used to carry (reed#35). Pinning 0.5.0 or newer
# is what makes the plain form below correct.
docker compose run --rm --no-deps -T \
  --volume "$PWD/${dir}:/backup:ro" \
  reed reed backup restore /backup/reed-backup.tar.gz

log "restoring qdrant snapshot into ${COLLECTION}"
docker compose run --rm --no-deps -T \
  --volume "$PWD/${dir}:/backup:ro" \
  --volume "$PWD/scripts:/stack-scripts:ro" \
  reed python /stack-scripts/qdrant-snapshot.py restore "$COLLECTION" /backup/qdrant.snapshot

log "starting reed"
docker compose start reed >/dev/null
trap - EXIT

log "waiting for reed to become ready"
deadline=$((SECONDS + READY_TIMEOUT_SECONDS))
until curl -fsS "${REED_URL}/ready" >/dev/null 2>&1; do
  if ((SECONDS >= deadline)); then
    echo "reed never became ready within ${READY_TIMEOUT_SECONDS}s" >&2
    exit 1
  fi
  sleep 3
done

log "restore complete: ${dir}"
