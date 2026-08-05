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
# Reed's restore builds a scratch directory next to REED_DATA_DIR and renames
# it into place. With the service's read-only rootfs that scratch lands on /
# and fails, so the volume is mounted at /restore instead and REED_DATA_DIR
# pointed inside it: scratch and target then share the volume's filesystem.
docker compose run --rm --no-deps -T \
  --volume reed_data:/restore \
  --volume "$PWD/${dir}:/backup:ro" \
  -e REED_DATA_DIR=/restore/data \
  reed sh -c 'reed backup restore /backup/reed-backup.tar.gz \
    && (mv /restore/data/* /restore/data/.[!.]* /restore/ 2> /dev/null || true) \
    && rmdir /restore/data'

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
