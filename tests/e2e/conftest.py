"""Fixtures for the browser end-to-end tests.

The stack under test is the one docker compose brought up in CI: Reed on
127.0.0.1:8000 and Open WebUI on 127.0.0.1:3000, both overridable.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session")
def reed_url() -> str:
    return os.environ.get("REED_URL", "http://127.0.0.1:8000")


@pytest.fixture(scope="session")
def webui_url() -> str:
    return os.environ.get("WEBUI_URL", "http://127.0.0.1:3000")
