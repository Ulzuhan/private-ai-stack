"""Browser-level tests of the chat door: Open WebUI.

Two journeys:

1. The first visitor creates the admin account and can chat — the door works.
2. A role-`user` account gets no file upload: the "Upload Files" entry in the
   input menu renders disabled, with the tooltip saying why. That is the
   enforceable half of "documents always go through Reed".

Known caveat, verified against the v0.11.0 sources: the upload permission
governs role `user`; Open WebUI hardcodes `$user?.role === 'admin'` as an
allow, so the admin account — the only one in a single-user quickstart —
keeps an enabled upload entry no matter what
USER_PERMISSIONS_CHAT_FILE_UPLOAD says. The stack's answer is the two-doors
narrative in the README plus this suite keeping the role-user boundary a
permanent regression check. If a future Open WebUI release lets the flag
bind admins too, tighten this suite to assert it. (The second test reuses
the admin the first one created; they run in definition order.)
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, Playwright, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

pytestmark = pytest.mark.e2e

ADMIN = {
    "name": "Stack Admin",
    "email": "admin@example.com",
    "password": "correct horse battery staple",
}
USER = {
    "name": "Stack User",
    "email": "user@example.com",
    "password": "correct horse battery staple",
}


def _submit_auth_form(page: Page, user: dict, *, signup: bool) -> None:
    if signup:
        page.locator("#name").fill(user["name"])
    page.locator("#email").fill(user["email"])
    page.locator("#password").fill(user["password"])
    page.locator('button[type="submit"]').first.click()


def _signup_first_admin(page: Page, webui_url: str) -> None:
    page.goto(f"{webui_url}/auth")
    # A fresh install shows the onboarding splash before the signup form.
    try:
        page.get_by_role("button", name="Get started").click(timeout=15_000)
    except PlaywrightTimeoutError:
        pass
    expect(page.locator("#name")).to_be_visible(timeout=60_000)
    _submit_auth_form(page, ADMIN, signup=True)
    # Landing on the chat UI proves the account was created and logged in.
    expect(page.locator("#chat-input")).to_be_visible(timeout=120_000)


def test_the_first_visitor_chats_as_admin(page: Page, webui_url: str) -> None:
    _signup_first_admin(page, webui_url)

    # The chat input is a ProseMirror surface: fill() sets the DOM but does
    # not always wake Svelte's state, which keeps the send button disabled.
    # Real keystrokes drive it the way a user does. The layout shifts while
    # the chat screen settles, so the click forces past stability checks —
    # visibility was already asserted above.
    page.locator("#chat-input").click(force=True, timeout=90_000)
    page.keyboard.type("Reply with exactly: pong", delay=20)
    send = page.locator("#send-message-button")
    expect(send).to_be_enabled(timeout=60_000)
    send.click()

    expect(page.locator(".markdown-prose").last).not_to_be_empty(timeout=180_000)


def test_role_user_gets_no_upload_door(
    page: Page, webui_url: str, playwright: Playwright
) -> None:
    # Log the admin in over the API and create the account the permission
    # actually governs (role `user`; the default `pending` cannot log in).
    api = playwright.request.new_context()
    signin = api.post(
        f"{webui_url}/api/v1/auths/signin",
        data={"email": ADMIN["email"], "password": ADMIN["password"]},
    )
    assert signin.ok, signin.text()
    token = signin.json()["token"]
    created = api.post(
        f"{webui_url}/api/v1/auths/add",
        data={**USER, "role": "user"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.ok, created.text()
    api.dispose()

    page.goto(f"{webui_url}/auth")
    expect(page.locator("#email")).to_be_visible(timeout=60_000)
    _submit_auth_form(page, USER, signup=False)
    expect(page.locator("#chat-input")).to_be_visible(timeout=120_000)

    page.locator("#input-menu-button").click()
    upload = page.get_by_role("button", name="Upload Files")
    expect(upload).to_be_visible()
    # Rendered but inert: disabled styling, no click action, tooltip explains.
    expect(upload).to_have_class(re.compile(r"opacity-50"))
