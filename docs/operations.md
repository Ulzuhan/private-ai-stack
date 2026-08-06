# Operations

Day-to-day running, backup and restore, upgrades, and the two Open WebUI
behaviors that surprise people. Everything described here that can be
machine-checked is: the backup round-trip runs in CI on every PR.

## Starting, stopping, inspecting

```bash
docker compose up -d        # start (first run pulls the models)
docker compose ps           # health status per service
docker compose logs -f reed # follow one service
docker compose down         # stop, keep data
docker compose down -v      # stop and WIPE every volume
```

Readiness: Reed exposes `/ready` (the compose healthcheck uses it), the
other services healthcheck over TCP. `docker compose ps` shows
`(healthy)` when a service is actually usable — model-init is a one-shot
and is done when it exits with code 0.

## Backup and restore

Reed's registry (SQLite + stored originals) and Qdrant's vectors are two
halves of the same state. `backup.sh` never copies live volumes: it stops
Reed briefly, takes Reed's own archive (verified on creation), snapshots the
Qdrant collection, and labels both artifacts as one consistent pair:

```bash
./scripts/backup.sh            # backups/<utc-timestamp>/, keeps the last 5
./scripts/backup.sh before-upgrade   # custom labels are never pruned
```

Each backup directory contains `reed-backup.tar.gz`, `qdrant.snapshot`, a
`manifest.json`, and `images.txt` recording exactly which pinned images
produced the pair.

Restore into a wiped stack (Reed's restore refuses a non-empty data
directory, so the supported flow starts clean):

```bash
docker compose down -v
docker compose up -d
./scripts/restore.sh backups/<label>
```

**Robust alternative** when the Qdrant half is missing or suspect: restore
only the Reed archive, then rebuild the vectors from the stored originals —
slower (it re-embeds everything), consistency guaranteed:

```bash
docker compose run --rm --no-deps reed reed index reindex
```

The whole round-trip — backup, `down -v`, restore, and a smoke test proving
the restored document still answers with citations — runs in CI on every
pull request.

## Upgrades

- **Images.** Dependabot opens PRs bumping the pinned tags/digests; the
  security workflow scans exactly the pinned set on every PR, and the weekly
  re-scan catches CVEs published between bumps. Review, let CI run the stack
  and the E2E, merge.
- **Reed.** Reed versions its index fingerprint (embedding model, chunking,
  extraction pipeline). When an upgrade changes the fingerprint, rebuild the
  index from the stored originals with `reed index reindex` — do **not**
  re-upload documents. `reed index rollback` undoes a rebuild.
- **Models.** Change `GENERATION_MODEL` / `EMBEDDING_MODEL` in `.env`, pull
  the new pair with `docker compose run --rm model-init`, then
  `docker compose up -d` to recreate the affected services. Changing the
  embedding model changes Reed's index fingerprint — reindex afterwards.
  Note that `embeddinggemma` is distributed under the Gemma Terms of Use,
  not an OSS license; that matters if you redistribute model weights (the
  air-gap bundle carries the terms — see [air-gap.md](air-gap.md)).

## Open WebUI: PersistentConfig gotcha

Open WebUI writes most of its env vars into its internal database on first
boot and silently ignores them afterwards. This stack sets
`ENABLE_PERSISTENT_CONFIG=false`, so the compose file stays the source of
truth — but only for volumes created with that flag in place.

If you booted once without it (an old volume from before the flag, or a
hand-rolled first run), later env changes do nothing. Two ways out:

1. Wipe the Open WebUI volume (you lose its accounts and chats):
   `docker compose down`, `docker volume rm private-ai-stack_open_webui_data`,
   `docker compose up -d`.
2. Or keep the volume and change the equivalent settings from its admin
   panel instead of env vars.

## File uploads and the admin caveat

`USER_PERMISSIONS_CHAT_FILE_UPLOAD=false` governs accounts with role
`user`: they see "Upload Files" disabled, with the tooltip explaining why —
the browser E2E asserts exactly this on every PR. The permission does **not**
bind the admin: Open WebUI hardcodes an allow for `role === 'admin'`
(verified against the v0.11.0 sources), and the first account created is the
admin. So in a single-user quickstart, that one person keeps an enabled
upload entry.

Operationally: the rule "documents go to Reed" is a convention the admin
must honor; for everyone else it is enforced. If a future Open WebUI release
lets the flag bind admins too, the E2E suite will be tightened to assert it.

## Exposing the stack beyond localhost

The quickstart binds both UIs to `127.0.0.1` and that is the supported
default. Before publishing any port further:

- set a strong ASCII `REED_API_KEY` (Reed's own rate limits —
  60 asks/min, 20 uploads/min by default — do the rest);
- front Open WebUI with TLS and restrict who can reach it — the first
  visitor to an unprotected instance becomes its admin.

A production override (Caddy terminating TLS + basic auth, clean routes to
both doors) is on the v0.1.0 roadmap and will be the documented way to do
this.

## Monitoring

Deliberately basic in v0.1: `docker compose ps` for health,
`docker compose logs` for detail, Reed's `/ready` for automation. There is
no tracing/metrics stack because nothing in the stack emits traces yet —
shipping an empty dashboard would say the opposite of what this repo
demonstrates. Real observability (Langfuse, instrumenting Reed upstream and
Open WebUI via its pipelines) is the v0.2 roadmap item.
