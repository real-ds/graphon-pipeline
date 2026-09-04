# Docs index

This folder holds every document relevant to building, evaluating, and submitting
this assessment. Keep it as the single place graders/reviewers look.

| File | Purpose |
|---|---|
| `ASSESSMENT_BRIEF.md` | Verbatim copy of the original brief (source of truth for requirements). |
| `PROJECT_PLAN.md` | Day-by-day execution plan across the 3-day trial window. |
| `architecture.md` | The graded Phase VI deliverable (max 3 pages) — scale, 413/429 handling, freshness, storage. |
| `SCHEMA.md` | Human-readable version of the canonical JSON schemas (mirrors `src/schemas/`). |
| `DECISIONS.md` | Running log of judgment calls made under ambiguity, per AGENT.md's guidance. |
| `EVALUATION_CHECKLIST.md` | Self-check against the brief's own weighted evaluation criteria before submitting. |
| `SUBMISSION_CHECKLIST.md` | Final checklist for the two required deliverables (Sheet + GitHub repo). |

`architecture.pdf` (the actual submitted deliverable) should be generated from
`architecture.md` right before submission, e.g.:

```bash
pandoc docs/architecture.md -o docs/architecture.pdf
```
