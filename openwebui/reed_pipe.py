"""
title: Reed Documents
author: private-ai-stack
author_url: https://github.com/Ulzuhan/private-ai-stack
version: 0.2.0
description: >-
  Ask the documents in Reed — the stack's RAG pipeline — without leaving the
  chat. Reed generates the calibrated answer with its [n] markers, every
  source arrives as a clickable citation card, and when the evidence is not
  there Reed's refusal is passed through untouched.
"""

import asyncio

import aiohttp
from pydantic import BaseModel, Field

# Reed's own limits (reed/api/schemas.py): longer histories are a 422 there,
# so the pipe truncates on its side and long chats keep working.
MAX_HISTORY_MESSAGES = 6
MAX_HISTORY_CONTENT_CHARS = 8_000
MAX_QUESTION_CHARS = 4_000

# Cold generation on consumer hardware can take minutes; Reed itself allows
# twice its provider timeout before answering 504, so the client waits longer.
ASK_TIMEOUT_SECONDS = 900


class Pipe:
    class Valves(BaseModel):
        REED_BASE_URL: str = Field(
            default="http://reed:8000",
            description=(
                "Reed's API, container-to-container. Only change this if Reed "
                "runs outside the compose network."
            ),
        )
        REED_API_KEY: str = Field(
            default="",
            description=(
                "Sent as X-API-Key when the stack sets REED_API_KEY. Empty "
                "matches the stack's default: no auth on the internal network."
            ),
        )
        REED_UI_URL: str = Field(
            default="http://127.0.0.1:8000",
            description=(
                "Where a browser reaches Reed's UI — citation cards link here, "
                "so it must be the host URL, not the container one."
            ),
        )

    def __init__(self):
        self.valves = self.Valves()

    @staticmethod
    def _text(content) -> str:
        """Message content is a string, or a list of parts for multimodal
        chats — keep only the text parts."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
        return ""

    def _question_and_history(self, body: dict):
        turns = [
            (message.get("role"), self._text(message.get("content", "")))
            for message in (body.get("messages") or [])
        ]
        turns = [
            (role, text)
            for role, text in turns
            if role in ("user", "assistant") and text.strip()
        ]
        if not turns or turns[-1][0] != "user":
            return None, []
        question = turns[-1][1][:MAX_QUESTION_CHARS]
        history = [
            {"role": role, "content": text[:MAX_HISTORY_CONTENT_CHARS]}
            for role, text in turns[-(MAX_HISTORY_MESSAGES + 1) : -1]
        ]
        return question, history

    async def _emit(self, emitter, event: dict) -> None:
        if emitter is not None:
            await emitter(event)

    async def pipe(
        self,
        body: dict,
        __user__: dict = None,
        __event_emitter__=None,
        __event_call__=None,
        __metadata__: dict = None,
        __task__: str = None,
    ) -> str:
        # Open WebUI runs its background tasks (chat titles, follow-up
        # suggestions) through the selected model — which is this pipe. They
        # are not document questions; each one would waste a slow Reed lookup
        # on a meta-prompt, so answer them out of band. (__task__ arrives
        # from metadata.task — backend functions.py in the pinned v0.11.0.)
        if __task__:
            return "Reed Documents"

        question, history = self._question_and_history(body)
        if question is None:
            return "Send a question and I will look it up in Reed's documents."

        await self._emit(
            __event_emitter__,
            {
                "type": "status",
                "data": {"description": "Consulting Reed's documents…", "done": False},
            },
        )

        headers = {"content-type": "application/json"}
        if self.valves.REED_API_KEY:
            headers["X-API-Key"] = self.valves.REED_API_KEY
        payload = {"question": question, "history": history, "stream": False}
        url = f"{self.valves.REED_BASE_URL.rstrip('/')}/v1/ask"

        try:
            timeout = aiohttp.ClientTimeout(total=ASK_TIMEOUT_SECONDS)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        return await self._explain_error(response)
                    data = await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            await self._emit(
                __event_emitter__,
                {"type": "status", "data": {"description": "Reed unreachable", "done": True}},
            )
            return (
                f"Reed is not reachable at {self.valves.REED_BASE_URL}. "
                "Is the stack up? (`docker compose up -d`)"
            )

        for source in data.get("sources") or []:
            label = source.get("filename") or "document"
            if source.get("page"):
                label = f"{label}, page {source['page']}"
            elif source.get("section"):
                label = f"{label} — {source['section']}"
            await self._emit(
                __event_emitter__,
                {
                    "type": "citation",
                    "data": {
                        "document": [source.get("excerpt") or source.get("snippet") or ""],
                        "metadata": [
                            {"source": label, "url": self.valves.REED_UI_URL}
                        ],
                        "source": {"name": label, "url": self.valves.REED_UI_URL},
                    },
                },
            )

        await self._emit(
            __event_emitter__,
            {
                "type": "status",
                "data": {"description": "Answered from Reed's documents", "done": True},
            },
        )
        return data.get("answer") or "Reed returned an empty answer."

    async def _explain_error(self, response) -> str:
        """Turn Reed's (structured) errors into an actionable chat message."""
        try:
            detail = (await response.json()).get("detail") or ""
        except Exception:
            detail = ""
        if response.status in (401, 403):
            return (
                "Reed rejected the request (auth). The stack sets REED_API_KEY "
                "but this pipe's REED_API_KEY valve does not match it — fix "
                "the valve or rerun scripts/install-reed-pipe.sh."
            )
        if response.status == 429:
            return "Reed is rate-limiting questions right now — try again in a minute."
        if response.status == 504:
            return (
                "Reed's answer timed out — on consumer hardware the first "
                "question after boot can be slow while the model loads. "
                "Please ask again."
            )
        suffix = f": {detail}" if detail else ""
        return f"Reed could not answer (HTTP {response.status}){suffix}"
