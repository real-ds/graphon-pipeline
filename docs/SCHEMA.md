# Canonical Schema Reference

Source of truth is `src/schemas/` (Pydantic models) — this file is a
human-readable mirror for quick reference. If they ever disagree, the code wins;
update this file to match.

## Startup
| Field | Type | Notes |
|---|---|---|
| schemaVersion | string | "1.0" |
| recordType | string | fixed "STARTUP" |
| source.name | string | |
| source.url | url | required — traceability |
| content.entityName | string | **canonicalized** via EntityResolver before storage |
| content.data.employeeCount | int? | optional |
| collectedAt | timestamp | ISO-8601, UTC |

## Product
| Field | Type | Notes |
|---|---|---|
| content.startupName | string | canonicalized |
| content.pricingModel | enum | FREE / FREEMIUM / PAID / ENTERPRISE |

## Research Paper
| Field | Type | Notes |
|---|---|---|
| content.title | string | |
| content.authors | string[] | |
| content.paper_url | url | arxiv or PDF link |
| content.github_url | url? | |
| content.github_stars | int? | fetched live via GitHub API |
| content.published_date | timestamp | ISO-8601 |

## Job
| Field | Type | Notes |
|---|---|---|
| content.company | string | canonicalized |
| content.date | timestamp | must be within 24h freshness window |
| content.is_remote | bool | |
| content.role_family | string | e.g. "Engineering" |

## News (added — not in the original brief's schema table, but required for the
News output tab; modeled with the same rigor as Job/ResearchPaper)
| Field | Type | Notes |
|---|---|---|
| content.headline | string | |
| content.full_text | string | |
| content.published_date | timestamp | must be within 24h freshness window |
| content.related_entity | string? | canonicalized, if detected |

## Entity Mapping Log (audit trail — its own output tab)
| Field | Type | Notes |
|---|---|---|
| raw_name | string | as scraped |
| canonical_name | string | resolved form |
| method | enum | EXACT / ALIAS / FUZZY / NO_MATCH |
| confidence | float | 0.0–1.0 |
