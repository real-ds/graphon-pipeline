---
name: entity-resolution
description: Use when implementing or modifying src/entity_resolution/*.py — canonicalizing startup/product names, extending the seed list, or debugging false-positive/negative merges.
---

# Deterministic Entity Resolution

## Pipeline (apply in this order, cheapest/most-certain first)
1. **Exact normalize + match**: lowercase, strip legal suffixes
   (`Inc.`, `Inc`, `LLC`, `Ltd`, `Corp`, `, Inc.`), strip punctuation/extra
   whitespace, then look up in the canonical seed list. This alone resolves the
   brief's own example: "OpenAI" / "OpenAI, Inc." / "Open AI" → normalize both sides
   the same way and most of these collapse before fuzzy matching is even needed
   (note: "Open AI" needs the space removed too — normalize whitespace-insensitively
   for the comparison key, not just the display string).
2. **Alias table lookup**: seed list entries carry a `known_aliases` list for
   name changes/rebrands (e.g. "Facebook" → "Meta") that normalization alone can't
   catch. Check this before falling to fuzzy matching.
3. **Fuzzy match** (only if 1–2 didn't resolve it): token-sort-ratio or
   Jaro-Winkler against the canonical list, threshold ~90. Anything between
   ~80–90 goes to a `needs_review` bucket in the Entity Mapping Log rather than
   being auto-merged — silent wrong merges are worse than an unresolved entity for
   a graph product.
4. **No match**: keep the raw name as its own canonical entity (new entity), but
   still log it in the Entity Mapping Log as `raw == canonical` so the log is a
   complete audit trail, not just a list of corrections.

## Guardrails
- Never merge two entities on fuzzy match alone if they differ in a way that
  changes meaning (e.g. "OpenAI" vs "OpenAI Foundation" — different legal entity).
  When unsure, prefer under-merging (two separate rows) over over-merging (wrongly
  combined companies) — the brief scores precision here, not recall.
- Every resolution decision — exact, alias, fuzzy, or no-match — gets one row in
  the Entity Mapping Log tab: `raw_name, canonical_name, method, confidence`.
  This log itself is a graded deliverable, not just internal debug output.

## Seed list
`data/seed/canonical_entities.json` ships with a handful of examples — extend it
to the required ~50 known AI startups before relying on resolution quality. Include
`name`, `known_aliases`, and optionally `domain` (for future URL-based matching).

## What "done" looks like
- `resolver.resolve(raw_name) -> ResolutionResult(canonical, method, confidence)`
- Every Startup/Product record's `content.entityName` passes through this before
  storage, and every call is logged for the Entity Mapping Log export.
