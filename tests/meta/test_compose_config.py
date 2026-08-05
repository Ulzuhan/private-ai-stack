"""Machine-checkable invariants of the stack's compose files.

Everything this repo promises in its README — pinned images, loopback-only
ports, telemetry off, container hardening — must hold as code, not as prose.
If a promise becomes untestable, that is a bug in the test, not a reason to
drop the promise.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docker-compose.yml"
OVERRIDES = [ROOT / "docker-compose.byo.yml", ROOT / "docker-compose.ci.yml"]

PINNED_IMAGE = re.compile(r"^[\w./-]+:[\w.-]+@sha256:[0-9a-f]{64}$")
LONG_RUNNING = ["ollama", "qdrant", "reed", "open-webui"]


@pytest.fixture(scope="module")
def services() -> dict:
    return yaml.safe_load(BASE.read_text(encoding="utf-8"))["services"]


def _env_pairs(service: dict) -> dict[str, str | None]:
    """Normalize list- and mapping-style environment blocks."""
    env = service.get("environment") or {}
    if isinstance(env, dict):
        return {key: (None if value is None else str(value)) for key, value in env.items()}
    pairs: dict[str, str | None] = {}
    for entry in env:
        name, _, value = entry.partition("=")
        pairs[name] = value if _ else None
    return pairs


def test_every_image_is_pinned_by_tag_and_digest(services: dict) -> None:
    for name, service in services.items():
        image = service.get("image", "")
        assert PINNED_IMAGE.match(image), f"{name}: image not pinned by tag + digest: {image}"


def test_no_override_replaces_an_image_with_an_unpinned_one() -> None:
    for override in OVERRIDES:
        data = yaml.safe_load(override.read_text(encoding="utf-8"))
        for name, service in (data.get("services") or {}).items():
            if "image" in service:
                assert PINNED_IMAGE.match(service["image"]), f"{override.name}: {name} unpinned"


def test_published_ports_bind_loopback_only(services: dict) -> None:
    for name, service in services.items():
        for port in service.get("ports") or []:
            port = port if isinstance(port, str) else str(port.get("published", ""))
            assert port.startswith("127.0.0.1:"), f"{name}: port not bound to loopback: {port}"


def test_long_running_services_have_healthchecks_and_restart_policies(services: dict) -> None:
    for name in LONG_RUNNING:
        service = services[name]
        assert "healthcheck" in service, f"{name}: no healthcheck"
        assert service.get("restart") == "unless-stopped", f"{name}: unexpected restart policy"


def test_model_init_is_a_one_shot(services: dict) -> None:
    assert str(services["model-init"].get("restart")) == "no"


def test_reed_keeps_the_hardening_it_shipped_with(services: dict) -> None:
    """The stack cannot be less strict than the service it integrates."""
    reed = services["reed"]
    assert reed.get("read_only") is True
    assert reed.get("init") is True
    assert "ALL" in (reed.get("cap_drop") or [])
    assert "no-new-privileges:true" in (reed.get("security_opt") or [])
    assert reed.get("tmpfs"), "reed: upload spool must be a bounded tmpfs"


def test_every_service_drops_something(services: dict) -> None:
    for name, service in services.items():
        hardening = set(service.get("security_opt") or []) | set(service.get("cap_drop") or [])
        assert hardening, f"{name}: no security_opt/cap_drop hardening at all"


def test_reed_runs_its_local_profile(services: dict) -> None:
    """Without REED_PROFILE=local Reed starts in its OpenAI profile and the
    stack silently stops being local."""
    env = _env_pairs(services["reed"])
    assert env.get("REED_PROFILE") == "local"


def test_reed_keeps_automatic_embedding_presets_unset(services: dict) -> None:
    env = _env_pairs(services["reed"])
    for knob in ["REED_MIN_EVIDENCE_SCORE", "REED_EMBED_QUERY_PREFIX", "REED_EMBED_DOC_PREFIX"]:
        assert knob in env, f"reed: {knob} must be a bare pass-through entry"
        assert env[knob] is None, f"reed: {knob} must stay unset to keep the calibrated preset"


def test_telemetry_is_off_everywhere(services: dict) -> None:
    assert _env_pairs(services["qdrant"]).get("QDRANT__TELEMETRY_DISABLED") == "true"
    webui = _env_pairs(services["open-webui"])
    expected = {
        "OFFLINE_MODE": "true",
        "ENABLE_OPENAI_API": "false",
        "SCARF_NO_ANALYTICS": "true",
        "DO_NOT_TRACK": "true",
        "ANONYMIZED_TELEMETRY": "false",
    }
    for key, value in expected.items():
        assert webui.get(key) == value, f"open-webui: {key} should be {value}"


def test_open_webui_cannot_become_a_second_rag_door(services: dict) -> None:
    webui = _env_pairs(services["open-webui"])
    assert webui.get("USER_PERMISSIONS_CHAT_FILE_UPLOAD") == "false"
    # Without this, every flag above is written to the internal database once
    # and silently ignored afterwards.
    assert webui.get("ENABLE_PERSISTENT_CONFIG") == "false"
