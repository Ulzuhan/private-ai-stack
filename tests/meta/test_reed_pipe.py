"""The Reed pipe is a feature of this repo: pin its contract as code.

The pipe file is installed into Open WebUI by scripts/install-reed-pipe.sh
against the functions REST API of the pinned Open WebUI image. Both sides of
that contract rot silently without checks — a refactor that drops the citation
emitter, or an installer that stops mirroring REED_API_KEY into the valves,
would only be noticed by a user in the chat. Everything cheap to assert is
asserted here; the live install runs in the stack CI job.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PIPE = ROOT / "openwebui" / "reed_pipe.py"
INSTALLER = ROOT / "scripts" / "install-reed-pipe.sh"
ENV_EXAMPLE = ROOT / ".env.example"


def test_the_pipe_file_is_valid_python() -> None:
    source = PIPE.read_text(encoding="utf-8")
    compile(source, str(PIPE), "exec")


def test_the_pipe_is_a_proxy_of_reeds_ask_endpoint() -> None:
    """The design decision as code: Reed generates the calibrated answer (with
    its audit and its refusals); the pipe is a thin protocol adapter, never a
    second RAG. `/v1/search` + own generation would duplicate Reed's brain."""
    source = PIPE.read_text(encoding="utf-8")
    assert 'title: Reed Documents' in source
    assert re.search(r"class Pipe:", source)
    assert re.search(r"class Valves\(BaseModel\):", source)
    assert 'default="http://reed:8000"' in source, (
        "the pipe's REED_BASE_URL default must be the compose-internal address"
    )
    assert "/v1/ask" in source
    assert '"stream": False' in source, "v0.2.0 is the non-streaming proxy"
    assert "/v1/search" not in source, (
        "retrieval-without-generation is for callers with their own model; the pipe proxies /v1/ask"
    )


def test_the_pipe_emits_native_citations() -> None:
    source = PIPE.read_text(encoding="utf-8")
    assert '"type": "citation"' in source
    assert '"document":' in source and '"metadata":' in source


def test_the_pipe_respects_reeds_history_limits() -> None:
    """reed/api/schemas.py rejects longer histories with a 422; the pipe
    truncates client-side. If Reed's limits move, move these too."""
    source = PIPE.read_text(encoding="utf-8")
    assert "MAX_HISTORY_MESSAGES = 6" in source
    assert "MAX_HISTORY_CONTENT_CHARS = 8_000" in source
    assert "MAX_QUESTION_CHARS = 4_000" in source


def test_open_webui_accepts_api_keys_for_the_installer() -> None:
    """ENABLE_API_KEYS defaults to False upstream (v0.11.0 config.py); the
    documented install path authenticates with an admin API key."""
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    env = compose["services"]["open-webui"].get("environment") or {}
    assert env.get("ENABLE_API_KEYS") == "true"


def test_the_installer_uses_the_functions_api_without_the_destructive_sync() -> None:
    """`/sync` reconciles by deleting every function not in the payload; the
    installer must touch only its own function, idempotently."""
    source = INSTALLER.read_text(encoding="utf-8")
    assert "openwebui/reed_pipe.py" in source
    assert "reed_documents" in source
    for endpoint in ["functions/create", "/update", "/toggle", "/valves/update"]:
        assert endpoint in source, f"installer does not call {endpoint}"
    assert "functions/sync" not in source


def test_the_installer_mirrors_the_stacks_reed_api_key() -> None:
    """One source of truth: the pipe's REED_API_KEY valve comes from the same
    .env variable Reed itself reads."""
    source = INSTALLER.read_text(encoding="utf-8")
    assert "WEBUI_ADMIN_API_KEY" in source
    assert "REED_API_KEY" in source


def test_the_admin_key_is_documented_but_never_shipped() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert re.search(r"^WEBUI_ADMIN_API_KEY=$", text, re.MULTILINE), (
        ".env.example must document WEBUI_ADMIN_API_KEY with an empty value"
    )
