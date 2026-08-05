"""Keep the workflows honest: required checks, pinned actions, concurrency.

The branch ruleset and the CI workflow must name the same checks — a job
renamed in the workflow silently stops being required, and a check renamed
in the ruleset silently blocks every PR. Neither is visible until it hurts,
so a machine compares them on every change.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

ACTION_REF = re.compile(r"uses:\s*([\w.-]+/[\w./-]+)@(\S+)")
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
CONCURRENCY_GROUP = re.compile(r"^concurrency:\n  group: (.+)$", re.MULTILINE)


def _ci_job_names() -> set[str]:
    data = yaml.safe_load((WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))
    return {job["name"] for job in data["jobs"].values()}


def _required_check_contexts() -> set[str]:
    if shutil.which("gh") is None:
        pytest.skip("gh CLI not available")
    repo = os.environ.get("GITHUB_REPOSITORY", "Ulzuhan/private-ai-stack")
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/rules/branches/main"],
            capture_output=True,
            check=True,
            text=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        pytest.skip(f"branch rules not readable: {error}")
    rules = json.loads(result.stdout)
    for rule in rules:
        if rule.get("type") == "required_status_checks":
            checks = rule["parameters"]["required_status_checks"]
            return {check["context"] for check in checks}
    pytest.fail("main has no required_status_checks rule — branch protection is gone")


def test_required_checks_match_ci_job_names() -> None:
    jobs = _ci_job_names()
    required = _required_check_contexts()
    assert jobs == required, (
        f"ci.yml jobs {sorted(jobs)} != required checks {sorted(required)} — "
        "update the ruleset or the workflow so they name the same checks"
    )


def test_every_action_is_pinned_by_full_sha() -> None:
    offenders: list[str] = []
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        for action, ref in ACTION_REF.findall(workflow.read_text(encoding="utf-8")):
            # Local reusable workflows (./...) are matched by the regex never;
            # anything reaching here is a remote action.
            if not FULL_SHA.match(ref):
                offenders.append(f"{workflow.name}: {action}@{ref}")
    assert not offenders, f"actions not pinned by full SHA: {offenders}"


def test_every_workflow_declares_a_distinct_concurrency_group() -> None:
    groups: list[str] = []
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        match = CONCURRENCY_GROUP.search(workflow.read_text(encoding="utf-8"))
        assert match is not None, f"{workflow.name} declares no concurrency group"
        groups.append(match.group(1))
    assert len(set(groups)) == len(groups), f"workflows share a group: {groups}"
