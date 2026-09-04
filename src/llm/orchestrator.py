"""Multi-tier LLM extraction engine: Gemini Flash -> Groq Llama 3 -> DeepSeek.

See .claude/skills/llm-fallback-chain/SKILL.md for the design rationale before
modifying this file.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from ..config import settings
from ..logger import get_logger
from ..utils.retry import PayloadTooLargeError, RateLimitError, retry_with_backoff
from .chunking import truncate_to_budget
from .prompts import build_extraction_prompt
from .providers import LLMProvider, build_provider_chain

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass
class ExtractionResult:
    record: Optional[BaseModel]
    provider_used: Optional[str]
    attempts: int
    failed: bool
    error: Optional[str] = None


class LLMOrchestrator:
    def __init__(self, providers: Optional[list[LLMProvider]] = None) -> None:
        self.providers = providers or build_provider_chain()

    async def extract(
        self,
        *,
        raw_text: str,
        title: str,
        target_schema: Type[T],
    ) -> ExtractionResult:
        """Run raw_text through the provider chain until one returns a
        schema-valid record, or every provider is exhausted.
        """
        schema_json = json.dumps(target_schema.model_json_schema())
        total_attempts = 0

        for provider in self.providers:
            content = truncate_to_budget(
                raw_text, title=title, max_tokens=settings.llm_max_input_tokens
            )
            prompt = build_extraction_prompt(schema_json=schema_json, content=content)

            try:
                raw_response = await retry_with_backoff(
                    lambda p=provider, pr=prompt: p.complete(pr),
                    max_attempts=settings.llm_max_retries_per_provider,
                    base=settings.llm_backoff_base_seconds,
                    cap=settings.llm_backoff_cap_seconds,
                    retry_on=(RateLimitError,),
                )
            except PayloadTooLargeError:
                # Shrink harder and retry once against the SAME provider before
                # falling through — a 413 doesn't mean the provider is unusable.
                logger.warning("413 from %s, retrying with a smaller chunk", provider.name)
                content = truncate_to_budget(
                    raw_text,
                    title=title,
                    max_tokens=settings.llm_max_input_tokens // 2,
                )
                prompt = build_extraction_prompt(schema_json=schema_json, content=content)
                try:
                    raw_response = await provider.complete(prompt)
                except Exception as exc:  # noqa: BLE001 - fall through to next provider
                    total_attempts += 1
                    logger.warning("%s failed after shrink: %s", provider.name, exc)
                    continue
            except Exception as exc:  # noqa: BLE001 - provider exhausted, try next
                total_attempts += 1
                logger.warning("%s exhausted retries: %s", provider.name, exc)
                continue

            total_attempts += 1
            record_or_none = self._validate(raw_response, target_schema, provider.name)
            if record_or_none is not None:
                return ExtractionResult(
                    record=record_or_none,
                    provider_used=provider.name,
                    attempts=total_attempts,
                    failed=False,
                )
            # Schema-invalid output is NOT a success — fall through to next provider.

        return ExtractionResult(
            record=None,
            provider_used=None,
            attempts=total_attempts,
            failed=True,
            error="All providers exhausted or returned schema-invalid output",
        )

    @staticmethod
    def _validate(
        raw_response: str, target_schema: Type[T], provider_name: str
    ) -> Optional[T]:
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned
        try:
            data = json.loads(cleaned)
            return target_schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("%s returned schema-invalid output: %s", provider_name, exc)
            return None
