"""Keep the changelog and the release pipeline honest.

release.yml trusts the changelog: the tag must name its newest versioned
section, and the release notes are extracted from it. Those guarantees only
hold if the file keeps a strict shape, so a machine checks that shape on
every change — a changelog that drifted would fail at tag time, the worst
possible moment to discover it.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CHANGELOG = ROOT / "CHANGELOG.md"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"

VERSION_HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+)\] - (\d{4}-\d{2}-\d{2})$", re.MULTILINE)
LINK_REF = re.compile(r"^\[([^\]]+)\]: (\S+)$", re.MULTILINE)


def _text() -> str:
    assert CHANGELOG.is_file(), "CHANGELOG.md is missing"
    return CHANGELOG.read_text(encoding="utf-8")


def test_changelog_keeps_a_versioned_newest_section() -> None:
    text = _text()
    assert "## [Unreleased]" in text
    headings = VERSION_HEADING.findall(text)
    assert headings, "no '## [x.y.z] - date' section found"
    versions = [version for version, _ in headings]
    assert versions == sorted(versions, key=lambda v: [int(p) for p in v.split(".")], reverse=True), (
        f"version sections out of order: {versions}"
    )


def test_every_version_heading_has_a_link_reference() -> None:
    text = _text()
    refs = dict(LINK_REF.findall(text))
    for name in ["Unreleased", *[v for v, _ in VERSION_HEADING.findall(text)]]:
        assert name in refs, f"[{name}] has no link reference at the bottom"
        assert refs[name].startswith(
            "https://github.com/Ulzuhan/private-ai-stack/"
        ), f"[{name}] points somewhere unexpected: {refs[name]}"


def test_release_workflow_validates_and_attests() -> None:
    assert RELEASE.is_file(), "release.yml is missing — the tag pipeline is gone"
    data = yaml.safe_load(RELEASE.read_text(encoding="utf-8"))
    trigger = data["on"] if "on" in data else data[True]
    assert trigger["push"]["tags"] == ["v*"]
    text = RELEASE.read_text(encoding="utf-8")
    # The guarantees the pipeline must not lose: tag checked against the
    # changelog and against main, and the published bundle attested.
    assert "CHANGELOG.md" in text
    assert "attest-build-provenance" in text
    assert "origin/main" in text
