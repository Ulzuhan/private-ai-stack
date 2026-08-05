"""Create or restore a Qdrant collection snapshot over the REST API.

Qdrant is deliberately not exposed on the host, so scripts/backup.sh and
scripts/restore.sh run this inside the Reed container, which sits on the
stack's network and already ships httpx. Not meant to be used directly.
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create", "restore"])
    parser.add_argument("collection")
    parser.add_argument("path", help="file to write (create) or to read (restore)")
    args = parser.parse_args()

    base_url = os.environ.get("QDRANT_INTERNAL_URL", "http://qdrant:6333")
    client = httpx.Client(base_url=base_url, timeout=600)

    if args.action == "create":
        response = client.post(f"/collections/{args.collection}/snapshots")
        response.raise_for_status()
        name = response.json()["result"]["name"]
        with (
            client.stream("GET", f"/collections/{args.collection}/snapshots/{name}") as stream,
            open(args.path, "wb") as handle,
        ):
            stream.raise_for_status()
            for chunk in stream.iter_bytes():
                handle.write(chunk)
        print(f"snapshot {name} written to {args.path}")
        return 0

    with open(args.path, "rb") as handle:
        response = client.post(
            f"/collections/{args.collection}/snapshots/upload",
            params={"wait": "true"},
            files={"snapshot": handle},
        )
    response.raise_for_status()
    print(f"snapshot {args.path} restored into {args.collection}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
