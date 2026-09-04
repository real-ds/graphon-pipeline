"""Deterministic entity resolution: exact-normalize -> alias -> fuzzy -> no-match.

See .claude/skills/entity-resolution/SKILL.md for the design rationale.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .fuzzy_match import similarity

_LEGAL_SUFFIXES = re.compile(
    r"\b(inc\.?|llc\.?|ltd\.?|corp\.?|corporation|co\.?|gmbh|plc)\b\.?", re.IGNORECASE
)
_WHITESPACE = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9]")

FUZZY_AUTO_MERGE_THRESHOLD = 0.90
FUZZY_REVIEW_THRESHOLD = 0.80


def normalize_key(name: str) -> str:
    """Normalization used ONLY as a comparison key — never as the display name.
    Strips legal suffixes, punctuation, and whitespace so 'OpenAI', 'OpenAI, Inc.',
    and 'Open AI' all collapse to the same key.
    """
    s = name.lower().strip()
    s = _LEGAL_SUFFIXES.sub("", s)
    s = _NON_ALNUM.sub("", s)  # also removes spaces -> handles "Open AI" -> "OpenAI"
    return s


@dataclass
class ResolutionResult:
    canonical: str
    method: str  # "EXACT" | "ALIAS" | "FUZZY" | "NO_MATCH"
    confidence: float


class EntityResolver:
    def __init__(self, seed_path: Path) -> None:
        self._by_key: dict[str, str] = {}
        self._canonical_names: list[str] = []
        self._load_seed(seed_path)

    def _load_seed(self, seed_path: Path) -> None:
        entries = json.loads(seed_path.read_text())
        for entry in entries:
            canonical = entry["name"]
            self._canonical_names.append(canonical)
            self._by_key[normalize_key(canonical)] = canonical
            for alias in entry.get("known_aliases", []):
                self._by_key[normalize_key(alias)] = canonical

    def resolve(self, raw_name: str) -> ResolutionResult:
        if not raw_name or not raw_name.strip():
            return ResolutionResult(canonical=raw_name, method="NO_MATCH", confidence=0.0)

        key = normalize_key(raw_name)

        # 1. Exact / alias match on the normalized key (covers both cases at once —
        #    the seed loader already folds aliases into the same lookup table).
        if key in self._by_key:
            canonical = self._by_key[key]
            method = "EXACT" if normalize_key(canonical) == key else "ALIAS"
            return ResolutionResult(canonical=canonical, method=method, confidence=1.0)

        # 2. Fuzzy match against known canonical names.
        best_match: Optional[str] = None
        best_score = 0.0
        for canonical in self._canonical_names:
            score = similarity(raw_name, canonical)
            if score > best_score:
                best_score = score
                best_match = canonical

        if best_match and best_score >= FUZZY_AUTO_MERGE_THRESHOLD:
            return ResolutionResult(canonical=best_match, method="FUZZY", confidence=best_score)

        if best_match and best_score >= FUZZY_REVIEW_THRESHOLD:
            # Below auto-merge confidence: log for the Entity Mapping Log's
            # "needs_review" bucket, but do NOT silently merge — keep the raw
            # name as its own entity to avoid a false-positive merge.
            return ResolutionResult(
                canonical=raw_name, method="NO_MATCH", confidence=best_score
            )

        # 3. No match at all: the raw name becomes its own canonical entity.
        return ResolutionResult(canonical=raw_name, method="NO_MATCH", confidence=0.0)
