"""Keep `.env.example` in lockstep with the compose files.

A variable the compose files consume but nobody documented, and a documented
variable nothing consumes, are both silent papercuts for anyone deploying
this. Both directions are checked, across every compose file and override.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ENV_EXAMPLE = ROOT / ".env.example"
COMPOSE_FILES = [
    ROOT / "docker-compose.yml",
    ROOT / "docker-compose.byo.yml",
    ROOT / "docker-compose.ci.yml",
]

# ${VAR} and ${VAR:-default} interpolations.
INTERPOLATED = re.compile(r"\$\{([A-Z][A-Z0-9_]*)[^}]*\}")
# `# VAR=value` documents a deliberately commented knob.
ASSIGNMENT = re.compile(r"^#?\s*([A-Z][A-Z0-9_]*)\s*=", re.MULTILINE)


def _used() -> set[str]:
    used: set[str] = set()
    for compose in COMPOSE_FILES:
        text = compose.read_text(encoding="utf-8")
        used.update(INTERPOLATED.findall(text))
        # Bare list entries (`- REED_MIN_EVIDENCE_SCORE`) inside environment
        # blocks pass the host value through.
        data = yaml.safe_load(text)
        for service in (data.get("services") or {}).values():
            env = service.get("environment") or {}
            if isinstance(env, list):
                used.update(entry for entry in env if "=" not in entry)
    return used


def _documented() -> set[str]:
    return set(ASSIGNMENT.findall(ENV_EXAMPLE.read_text(encoding="utf-8")))


def test_every_compose_variable_is_documented() -> None:
    missing = _used() - _documented()
    assert not missing, f"compose variables missing from .env.example: {sorted(missing)}"


def test_every_documented_variable_is_used() -> None:
    unused = _documented() - _used()
    assert not unused, f".env.example documents variables nothing consumes: {sorted(unused)}"


def test_the_example_does_not_ship_a_real_key() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "sk-" not in text, ".env.example looks like it contains a real API key"
