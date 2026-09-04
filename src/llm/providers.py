"""LLM provider adapters. Each implements the same interface so the orchestrator
can treat Gemini/Groq/DeepSeek interchangeably. Fill in the marked TODOs with the
real SDK/HTTP calls for each provider once you have API keys — the interface and
error-classification contract are what matters and are already correct.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

import aiohttp

from ..config import settings
from ..utils.retry import PayloadTooLargeError, RateLimitError


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def complete(self, prompt: str) -> str:
        """Return the raw text completion. Must raise RateLimitError on HTTP 429
        and PayloadTooLargeError on HTTP 413 so the orchestrator can react correctly
        — do not swallow these into a generic exception.
        """
        raise NotImplementedError

    @staticmethod
    def _raise_for_status(status: int, body: str) -> None:
        if status == 429:
            raise RateLimitError(body)
        if status == 413:
            raise PayloadTooLargeError(body)
        if status >= 400:
            raise RuntimeError(f"Provider error {status}: {body[:500]}")


class GeminiProvider(LLMProvider):
    name = "gemini"
    _ENDPOINT = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent"
    )

    async def complete(self, prompt: str) -> str:
        params = {"key": settings.gemini_api_key}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        async with aiohttp.ClientSession() as session:
            async with session.post(self._ENDPOINT, params=params, json=payload) as resp:
                text = await resp.text()
                self._raise_for_status(resp.status, text)
                data = json.loads(text)
                return data["candidates"][0]["content"]["parts"][0]["text"]


class GroqProvider(LLMProvider):
    name = "groq"
    _ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
    _MODEL = "openai/gpt-oss-20b"

    async def complete(self, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
        payload = {
            "model": self._MODEL,
            "messages": [{"role": "user", "content": prompt}],
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self._ENDPOINT, headers=headers, json=payload) as resp:
                text = await resp.text()
                self._raise_for_status(resp.status, text)
                data = json.loads(text)
                return data["choices"][0]["message"]["content"]


class DeepSeekProvider(LLMProvider):
    name = "deepseek"
    _ENDPOINT = "https://api.deepseek.com/chat/completions"
    _MODEL = "deepseek-chat"

    async def complete(self, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {settings.deepseek_api_key}"}
        payload = {
            "model": self._MODEL,
            "messages": [{"role": "user", "content": prompt}],
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self._ENDPOINT, headers=headers, json=payload) as resp:
                text = await resp.text()
                self._raise_for_status(resp.status, text)
                data = json.loads(text)
                return data["choices"][0]["message"]["content"]


PROVIDER_REGISTRY: dict[str, type[LLMProvider]] = {
    "gemini": GeminiProvider,
    "groq": GroqProvider,
    "deepseek": DeepSeekProvider,
}


def build_provider_chain() -> list[LLMProvider]:
    return [PROVIDER_REGISTRY[name]() for name in settings.llm_provider_chain]
