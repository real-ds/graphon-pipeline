# Submission Checklist

## 1. Data Output (Google Sheets)
- [ ] Public link (view access, no login required to check).
- [ ] 6 tabs present: Startups, Products, Research Papers, Jobs, News, Entity
      Mapping Log.
- [ ] Startups ≥ 1,000 rows.
- [ ] Products ≥ 1,000 rows.
- [ ] Research Papers ≥ 1,000 rows, including GitHub stars column populated.
- [ ] Jobs: all found within the 24h window (spot-check a few dates).
- [ ] News: all found within the 24h window (spot-check a few dates).
- [ ] Entity Mapping Log: raw vs. canonical names, method, confidence populated.

## 2. Engineering Output (GitHub Repository)
- [ ] `README.md` — setup instructions + architecture overview (already in this
      scaffold; keep it accurate as you build).
- [ ] `src/` — crawler, LLM orchestrator, entity resolver source code.
- [ ] `architecture.pdf` — exported from `docs/architecture.md`, max 3 pages.
- [ ] Repo is public or shared with the reviewers per the submission form.
- [ ] `.env` is NOT committed; `.env.example` is.
- [ ] `data/seed/canonical_entities.json` reflects your final ~50-entity list.

## Submit both links via the form
https://forms.gle/8bnrg78Ki4E25RAk8
