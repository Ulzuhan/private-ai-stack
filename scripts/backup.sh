#!/usr/bin/env bash
# Create a consistent backup pair: Reed's own archive (registry + stored
# originals) plus a snapshot of the Qdrant collection, labeled together.
# Reed state and Qdrant chunks are two halves of the same state — never back
# up one without the other, and never copy live volumes.
#
#   ./scripts/backup.sh [label]        # default label: UTC timestamp
#
# Output: backups/<label>/{reed-backup.tar.gz, qdrant.snapshot, manifest.json}
# Timestamped labels are rotated (KEEP_BACKUPS, default 5); custom labels are
# never pruned.
set -euo pipefail

BACKUP_ROOT=${BACKUP_ROOT:-backups}
KEEP_BACKUPS=${KEEP_BACKUPS:-5}
COLLECTION=${REED_COLLECTION:-reed_chunks}

label=${1:-$(date -u +%Y%m%dT%H%M%SZ)}
dir="${BACKUP_ROOT}/${label}"

log() { printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*"; }

if [ -e "$dir" ]; then
  echo "backup already exists: ${dir}" >&2
  exit 1
fi
mkdir -p "$dir"
# Reed runs as its own unprivileged user inside the container; the bind mount
# must be writable by whatever uid that maps to on this host.
chmod 0777 "$dir"

# Reed's archive is only consistent while the server is stopped (SQLite), so
# the service goes down for the duration of the backup and always comes back.
log "stopping reed"
docker compose stop reed
trap 'docker compose start reed > /dev/null' EXIT

log "creating reed archive"
docker compose run --rm --no-deps -T \
  --volume "$PWD/${dir}:/backup" \
  reed reed backup create /backup/reed-backup.tar.gz

log "verifying reed archive"
docker compose run --rm --no-deps -T \
  --volume "$PWD/${dir}:/backup" \
  reed reed backup verify /backup/reed-backup.tar.gz

log "snapshotting qdrant collection ${COLLECTION}"
docker compose run --rm --no-deps -T \
  --volume "$PWD/${dir}:/backup" \
  --volume "$PWD/scripts:/stack-scripts:ro" \
  reed python /stack-scripts/qdrant-snapshot.py create "$COLLECTION" /backup/qdrant.snapshot

# The label and timestamp are what tie the two halves together; images.txt
# records exactly which pinned images produced this pair.
{
  printf '{\n'
  printf '  "label": "%s",\n' "$label"
  printf '  "created_at": "%s",\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '  "collection": "%s",\n' "$COLLECTION"
  printf '  "files": ["reed-backup.tar.gz", "qdrant.snapshot"]\n'
  printf '}\n'
} >"${dir}/manifest.json"
docker compose config --images | sort -u >"${dir}/images.txt"

# Simple rotation of timestamped runs; custom labels are left alone.
if [ "$KEEP_BACKUPS" -gt 0 ]; then
  shopt -s nullglob
  timestamped=()
  for entry in "$BACKUP_ROOT"/*; do
    name=${entry##*/}
    if [[ $name =~ ^[0-9]{8}T[0-9]{6}Z$ ]]; then
      timestamped+=("$name")
    fi
  done
  if ((${#timestamped[@]} > KEEP_BACKUPS)); then
    mapfile -t sorted < <(printf '%s\n' "${timestamped[@]}" | sort -r)
    for old in "${sorted[@]:$KEEP_BACKUPS}"; do
      log "pruning old backup ${old}"
      rm -rf "${BACKUP_ROOT:?}/${old}"
    done
  fi
fi

log "backup pair complete: ${dir}"
