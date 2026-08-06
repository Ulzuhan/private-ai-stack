"""Keep config/models.yaml honest: it is the single source of truth for
which models each profile runs, and the air-gap packager trusts its license
entries to redistribute weights legally. If the catalog drifts from the
compose defaults or the CI model, the wrong thing ships — so a machine
compares them on every change.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CATALOG = yaml.safe_load((ROOT / "config" / "models.yaml").read_text(encoding="utf-8"))

DEFAULT = re.compile(r"\$\{(GENERATION_MODEL|EMBEDDING_MODEL):-([^}]+)\}")


def _compose_defaults(filename: str) -> dict[str, str]:
    """The GENERATION_MODEL/EMBEDDING_MODEL defaults a compose file would use
    on its own. A file that mentions a variable without re-defaulting it does
    not change the default."""
    text = (ROOT / filename).read_text(encoding="utf-8")
    return {match.group(1): match.group(2) for match in DEFAULT.finditer(text)}


def test_cpu_profile_matches_the_base_compose_defaults() -> None:
    defaults = _compose_defaults("docker-compose.yml")
    profile = CATALOG["profiles"]["cpu"]
    assert defaults["GENERATION_MODEL"] == profile["generation"]
    assert defaults["EMBEDDING_MODEL"] == profile["embedding"]


def test_gpu_profile_matches_the_gpu_override_default() -> None:
    # The override only re-defaults what changes; anything it does not
    # mention keeps the base file's default.
    base = _compose_defaults("docker-compose.yml")
    defaults = {**base, **_compose_defaults("docker-compose.gpu.yml")}
    profile = CATALOG["profiles"]["gpu"]
    assert defaults["GENERATION_MODEL"] == profile["generation"]
    assert defaults["EMBEDDING_MODEL"] == profile["embedding"]


def test_ci_profile_matches_the_ci_workflow_model() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    profile = CATALOG["profiles"]["ci"]
    for job in workflow["jobs"].values():
        model = (job.get("env") or {}).get("GENERATION_MODEL")
        if model is not None:
            assert model == profile["generation"], (
                f"ci.yml runs {model} but the ci profile declares {profile['generation']}"
            )


def test_every_profiled_model_has_a_license_entry() -> None:
    """The air-gap bundle redistributes weights; an unlicensed model in the
    catalog is a legal bug, not a paperwork one."""
    models = CATALOG["models"]
    for profile_name, profile in CATALOG["profiles"].items():
        for kind in ("generation", "embedding"):
            model = profile[kind]
            entry = models.get(model)
            assert entry is not None, f"profiles.{profile_name}.{kind}: {model} has no models entry"
            assert entry.get("license"), f"{model}: no license"
            assert entry.get("license_url", "").startswith("https://"), f"{model}: no license_url"


def test_embeddinggemma_is_flagged_as_non_oss() -> None:
    """Gemma ships under Google's Terms of Use, not an OSS license — the
    catalog must keep saying so out loud."""
    entry = CATALOG["models"]["embeddinggemma"]
    assert "Gemma" in entry["license"]
    assert entry.get("note"), "embeddinggemma lost its non-OSS warning note"


@pytest.mark.parametrize("model", ["qwen3.5:4b", "qwen3.5:9b", "qwen3.5:0.8b"])
def test_qwen35_models_record_apache20(model: str) -> None:
    """Qwen publishes 3.5 as Apache-2.0; if that changes upstream, this test
    is the tripwire that forces the catalog (and the bundle) to catch up."""
    assert CATALOG["models"][model]["license"] == "Apache-2.0"
