"""Keep the documentation honest: pins, links, assets, and cross-references.

The README is the case study; if it drifts from the compose file (a bumped
image tag that only exists in one place) or points at files that do not
exist, a visitor notices before we do. Everything here is cheap to check
by machine, so a machine checks it on every change.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
README_ES = ROOT / "README.es.md"
DOCS = sorted((ROOT / "docs").glob("*.md"))
MARKDOWN_FILES = [README, README_ES, *DOCS]

# [text](target) and ![alt](target); target may carry an #anchor.
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
HEADER = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)


def _slug(header: str) -> str:
    """GitHub's anchor rule, close enough for our own headers."""
    text = re.sub(r"[^\w\- ]", "", header.strip().lower(), flags=re.UNICODE)
    return text.replace(" ", "-")


def _anchors(path: Path) -> set[str]:
    return {_slug(h) for h in HEADER.findall(path.read_text(encoding="utf-8"))}


def test_readme_lists_every_pinned_image() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    readme = README.read_text(encoding="utf-8")
    missing: list[str] = []
    for service in (compose.get("services") or {}).values():
        image = service.get("image", "")
        repo_tag = image.split("@", 1)[0]  # drop the digest
        if repo_tag and repo_tag not in readme:
            missing.append(repo_tag)
    assert not missing, (
        f"README.md does not mention these pinned images: {missing} — "
        "update the components table after a bump"
    )


def test_every_relative_markdown_link_resolves() -> None:
    broken: list[str] = []
    for source in MARKDOWN_FILES:
        for target in LINK.findall(source.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            path_part, _, anchor = target.partition("#")
            dest = source if not path_part else (source.parent / path_part)
            if not dest.exists():
                broken.append(f"{source.relative_to(ROOT)}: {target} (no such file)")
                continue
            if anchor and anchor not in _anchors(dest):
                broken.append(f"{source.relative_to(ROOT)}: {target} (no such anchor)")
    assert not broken, "broken markdown links:\n" + "\n".join(broken)


def test_readme_demo_gif_exists() -> None:
    assert "assets/demo.gif" in README.read_text(encoding="utf-8")
    gif = ROOT / "assets" / "demo.gif"
    assert gif.exists() and gif.stat().st_size > 0, "assets/demo.gif is missing"


def test_every_doc_is_linked_from_the_readme() -> None:
    readme = README.read_text(encoding="utf-8")
    orphans = [doc.name for doc in DOCS if f"docs/{doc.name}" not in readme]
    assert not orphans, f"docs not linked from README.md: {orphans}"


def test_spanish_readme_links_the_english_one() -> None:
    assert "README.md" in README_ES.read_text(encoding="utf-8")
