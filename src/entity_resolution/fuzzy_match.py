"""Fuzzy string matching, isolated behind one function so the underlying
algorithm/library can be swapped without touching resolver.py.

Uses `rapidfuzz` (in requirements.txt) — much faster than fuzzywuzzy and has no
GPL dependency (python-Levenshtein).
"""
from __future__ import annotations

from rapidfuzz import fuzz


def similarity(a: str, b: str) -> float:
    """Returns 0.0-1.0 token-sort-ratio similarity, robust to word reordering
    ('AI Startup Inc' vs 'Startup Inc AI') which plain Levenshtein is not.
    """
    return fuzz.token_sort_ratio(a, b) / 100.0
