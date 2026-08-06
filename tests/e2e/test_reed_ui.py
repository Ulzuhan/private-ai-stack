"""Browser-level test of the document door: Reed's own UI.

The same upload → ask → cited-answer flow the curl smoke covers, exercised
through the interface a user actually touches. Runs against the real models
the CI stack pulls, so timeouts are generous on purpose.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def test_upload_ask_and_cite_through_the_reed_ui(page: Page, reed_url: str) -> None:
    page.goto(reed_url)

    page.set_input_files(
        "#file-input",
        files={
            "name": "expenses.md",
            "mimeType": "text/markdown",
            "buffer": b"# Expenses policy\n\nExpenses above 75 euros require pre-approval.\n",
        },
    )
    expect(page.locator(".doc-name")).to_have_text("expenses.md")
    expect(page.locator(".doc-meta")).to_contain_text("chunks", timeout=180_000)

    page.locator("#question").fill("What is the expense pre-approval threshold?")
    page.locator("#send").click()

    answer = page.locator(".message.assistant .bubble").last
    expect(answer).not_to_be_empty(timeout=180_000)
    expect(page.locator(".message.assistant .source").last).to_be_visible(timeout=180_000)
