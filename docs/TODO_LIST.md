# 🚀 Job Matching Agent — TODO

> **v1 Goal:** `scrape → clean → extract → match → output (Sheets / CLI)`

---

## 🔴 P0 — Core System

### 1. Job Description Extraction
- [ ] Define multi-role behavior (A: split into multiple `JobProfile`s | B: dominant role only — *default v1*)
- [ ] Finalize `JobProfile` schema (strict + minimal, remove low-signal fields)
- [ ] Implement extraction pipeline: `analysis_text` → structured `JobProfile`
- [ ] Add extraction status: `pending / success / failed` + error logging

### 2. Matching System
- [ ] Hard filters: location, work auth, required skills
- [ ] Stage 1 — fast pre-filter: lightweight scoring, reduce candidate set
- [ ] Stage 2 — deep match: LLM scoring, return top N jobs
- [ ] Scoring output: `match_score`, `reasoning`, `key strengths / gaps`

### 3. Pipeline Orchestration
- [ ] Finalize `run_pipeline()`: load profile → fetch → clean → extract → match → output
- [ ] Ensure modular steps (no tight coupling)
- [ ] Add fail-fast checks (API keys, configs)

---

## 🟠 P1 — Data & Storage

### 4. Database Schema

| Table | Key Fields |
|---|---|
| `jobs` | `id`, `job_url`, `cleaned_text`, `metadata` |
| `job_content` | `job_id (FK)`, `profile_json`, `extraction_status`, `extraction_confidence` |
| `matches` | `user_id`, `job_id`, `match_score`, `stage (1\|2)`, `reasoning` |
| `actions` *(future)* | `applied / saved / skipped` |

- [ ] Add indexing on `job_id`, `role_family`, `seniority`

### 5. Migrations
- [ ] Add `schema_migrations` table with versioned, idempotent changes
- [ ] No destructive ALTERs in v1

---

## 🟡 P2 — Scraping & Prompts

### 6. Scraper
- [ ] Abstract scraper interface; normalize output across sources
- [ ] LinkedIn (existing) + Indeed / others (future)
- [ ] Handle anti-bot constraints at design level

### 7. Prompt Engineering
- [ ] Refactor extraction prompt (focus on signal, remove fluff)
- [ ] Improve: `role_family` classification, seniority detection, skill extraction
- [ ] Add confidence scoring

---

## 🟢 P3 — API & Testing

### 8. API
- [ ] `POST /profile`, `GET /matches`
- [ ] Auth (basic), rate limiting, input validation
- [ ] Keep API thin — call pipeline internally

### 9. Testing
- [ ] Unit: extraction, matching logic
- [ ] Integration: full pipeline run
- [ ] Edge cases: empty descriptions, duplicates, malformed inputs

---

## ⚪ P4 — Defer

- ❌ No cloud deployment
- ❌ No infra optimization
- ✅ Focus: **local, fast iteration**

---

## 🧠 Principles
**KISS · fast iteration · minimize LLM cost · build for real usage**

## ✅ Definition of Done (v1)
- [ ] Input: user resume / profile
- [ ] Output: top 5–10 matched jobs
- [ ] Pipeline runs end-to-end locally with **actually useful** results