"""Browser-level test of the "Reed Documents" pipe journey.

The user path, end to end: mint an admin API key, run the repo's installer,
pick "Reed Documents" in the model selector, ask about a document in Reed,
and get an answer whose sources are native, clickable citation cards. The
pipe itself and the installer's idempotency are covered in the stack CI job;
this file proves the browser half — model selectable, answer rendered,
citations expand and open.

Selectors verified against the pinned Open WebUI v0.11.0 sources, not
guessed (chat/ModelSelector/Selector.svelte, ModelSelector/ModelItem.svelte,
chat/Messages/Citations.svelte, Citations/CitationModal.svelte):

- The selector trigger is `button#model-selector-model-button`; the search
  field is `#model-search-input`; each model is
  `button[role="option"][data-value="<model id>"]`.
- Citations render as a pill `button[aria-expanded]` whose aria-label is
  "Toggle 1 source" / "Toggle N sources" — matched by the "*source*"
  substring so the sidebar's own toggle cannot collide — and start
  collapsed (`showCitations = false`), so the test expands them.
- Each source is `button[aria-label^="View source:"]`; clicking one opens
  the citation modal (dismissable via aria-label "Close citation modal").

Answer *quality* is never asserted: CI runs the 0.8b model, which proves the
circuit only. The citation cards come from Reed's sources regardless of how
well the tiny model phrases its markers.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, Playwright, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

pytestmark = pytest.mark.e2e

ADMIN = {
    "name": "Stack Admin",
    "email": "admin@example.com",
    "password": "correct horse battery staple",
}
DOC_NAME = "roof-garden.md"
DOC_TEXT = "# Roof garden\n\nThe office roof garden closes at 19:00 on weekdays.\n"
QUESTION = "When does the office roof garden close on weekdays?"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _admin_token(api, webui_url: str) -> str:
    signin = api.post(
        f"{webui_url}/api/v1/auths/signin",
        data={"email": ADMIN["email"], "password": ADMIN["password"]},
    )
    if signin.ok:
        return signin.json()["token"]
    # test_openwebui.py usually creates the admin first, but a fresh volume
    # must work too: the first signup is never gated upstream and becomes the
    # admin (v0.11.0 auths.py — "Don't gate the first admin on ENABLE_SIGNUP").
    signup = api.post(f"{webui_url}/api/v1/auths/signup", data=ADMIN)
    assert signup.ok, signup.text()
    return signup.json()["token"]


@pytest.fixture(scope="module")
def reed_document(playwright: Playwright, reed_url: str) -> str:
    """A document only this journey asks about, so retrieval cannot collide
    with the expenses policy the other suites upload."""
    api = playwright.request.new_context()
    try:
        upload = api.post(
            f"{reed_url}/v1/documents",
            multipart={
                "file": {
                    "name": DOC_NAME,
                    "mimeType": "text/markdown",
                    "buffer": DOC_TEXT.encode(),
                }
            },
        )
        assert upload.ok, upload.text()
        document_id = upload.json()["document_id"]
        status = "pending"
        for _ in range(90):
            doc = api.get(f"{reed_url}/v1/documents/{document_id}")
            assert doc.ok, doc.text()
            status = doc.json()["status"]
            if status == "ready":
                break
            assert status != "error", doc.text()
            time.sleep(2)
        assert status == "ready", f"ingestion never finished (last: {status})"
        return document_id
    finally:
        api.dispose()


@pytest.fixture(scope="module")
def installed_pipe(playwright: Playwright, webui_url: str, reed_document: str) -> None:
    """The documented install path, not a shortcut: mint an admin API key and
    run the repo's installer exactly as a user would. Depends on the document
    so the whole journey is ready before any browser opens."""
    api = playwright.request.new_context()
    try:
        token = _admin_token(api, webui_url)
        created = api.post(
            f"{webui_url}/api/v1/auths/api_key",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert created.ok, created.text()
        api_key = created.json()["api_key"]
    finally:
        api.dispose()
    env = {
        **os.environ,
        "WEBUI_ADMIN_API_KEY": api_key,
        "WEBUI_URL": webui_url,
    }
    result = subprocess.run(
        ["./scripts/install-reed-pipe.sh"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"


def _login_as_admin(page: Page, webui_url: str) -> None:
    page.goto(f"{webui_url}/auth")
    expect(page.locator("#email")).to_be_visible(timeout=60_000)
    page.locator("#email").fill(ADMIN["email"])
    page.locator("#password").fill(ADMIN["password"])
    page.locator('button[type="submit"]').first.click()
    expect(page.locator("#chat-input")).to_be_visible(timeout=120_000)
    # The "What's New" modal greets admins and swallows clicks while up; it
    # should not reappear after the first dismissal, but stay defensive.
    try:
        page.locator('button[aria-label="Close"]').first.click(timeout=10_000)
        expect(page.locator('[aria-modal="true"]')).to_have_count(0, timeout=15_000)
    except PlaywrightTimeoutError:
        pass


def _type_prompt(page: Page, prompt: str) -> None:
    # ProseMirror needs real keystrokes after a real click; verify by reading
    # the text back and retry instead of hoping (same pattern as the admin
    # journey — fill() does not wake Svelte's state).
    chat = page.locator("#chat-input")
    for _ in range(3):
        chat.click(timeout=90_000)
        page.keyboard.type(prompt, delay=20)
        try:
            expect(chat).to_contain_text(prompt, timeout=10_000)
            return
        except AssertionError:
            page.keyboard.press("ControlOrMeta+a")
            page.keyboard.press("Backspace")
    raise AssertionError("the chat input never accepted the typed prompt")


def test_reed_documents_model_answers_with_clickable_citations(
    page: Page, webui_url: str, installed_pipe: None
) -> None:
    _login_as_admin(page, webui_url)

    # Pick the pipe like any user would: selector, search, click the option.
    page.locator("button#model-selector-model-button").click()
    search = page.locator("#model-search-input")
    expect(search).to_be_visible(timeout=15_000)
    search.fill("Reed")
    option = page.locator('button[role="option"][data-value="reed_documents"]')
    expect(option).to_be_visible(timeout=15_000)
    option.click()
    expect(page.locator("button#model-selector-model-button")).to_contain_text(
        "Reed Documents"
    )

    _type_prompt(page, QUESTION)
    send = page.locator("#send-message-button")
    expect(send).to_be_enabled(timeout=60_000)
    send.click()

    # Generous: the pipe's HTTP hop plus a cold 0.8b generation on a CPU
    # runner can take minutes. The assertion is that an answer renders —
    # never its quality.
    answer = page.locator(".markdown-prose").last
    expect(answer).not_to_be_empty(timeout=300_000)

    # The feature: Reed's sources as native citation cards. The pill starts
    # collapsed; expand it, then open the first source's modal.
    pill = page.locator('button[aria-expanded][aria-label*="source"]').last
    expect(pill).to_be_visible(timeout=60_000)
    if pill.get_attribute("aria-expanded") == "false":
        pill.click()
    source = page.locator('button[aria-label^="View source:"]').first
    expect(source).to_be_visible(timeout=15_000)
    expect(source).to_contain_text(DOC_NAME)
    source.click()
    modal = page.locator('[aria-modal="true"]')
    # The excerpt is Reed's retrieved chunk verbatim — the one place in this
    # journey where the document's exact wording must appear.
    expect(modal).to_contain_text("19:00", timeout=15_000)
    expect(modal).to_contain_text(DOC_NAME)
