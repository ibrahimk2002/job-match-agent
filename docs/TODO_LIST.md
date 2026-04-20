# 🚀 Job Matching Agent — TODO

> **v1 Goal:** `ingest → extract once → deterministic match → optional rerank → output (CLI / Sheets)`

---

## 🔴 Immediate Goals

### 1. Finalize Matching Schema
- [ ] Update `job_profile.py` to match the new `job_profiles` table columns
- [ ] Add all denormalized fields required for stage 1 matching
- [ ] Add extraction metadata fields needed for versioning and auditability
- [ ] Keep the schema aligned with matching needs, not generic parsing completeness

### 2. Refactor Extraction Prompt
- [ ] Update the extraction prompt so it supports every field needed for matching
- [ ] Keep the prompt lean and execution-oriented
- [ ] Improve prompt instructions for hard-filter fields, seniority interpretation, and matching signals
- [ ] Reduce fluff so extraction remains cheap, stable, and repeatable

### 3. Update Job Extraction Flow
- [ ] Ensure extraction writes the full structured profile plus matching-critical metadata
- [ ] Confirm extraction output shape cleanly matches the database save layer

### 4. Validate Job-Side Flow End-to-End
- [ ] Verify migration + backfill output still works with the updated schema
- [ ] Test ingestion → extraction → persistence into `job_profiles`
- [ ] Validate active profile logic, version metadata, and required denormalized columns
- [ ] Verify everything up to stage 1 readiness works correctly before moving further

### 5. Update User Profile Schema
- [ ] Refactor `user_profile` schema for stronger matching accuracy
- [ ] Add fields needed to compare directly against `job_profiles`
- [ ] Make hard-filter preferences and role-fit signals explicit
- [ ] Keep it practical for early-career matching, not over-engineered

### 6. Implement User Profile Extraction
- [ ] Build the extraction flow for `user_profile`
- [ ] Decide whether to reuse job-style extraction logic or keep user extraction separate
- [ ] Support resume/profile input → structured `user_profile`
- [ ] Ensure the resulting schema is directly usable by stage 1 matching

### 7. Make Stage 1 Matching Runnable
- [ ] Implement stage 1 against denormalized columns only
- [ ] Add hard filters: work auth, sponsorship, location, work mode, degree, clearly strict YOE
- [ ] Add cheap scoring: role fit, skills overlap, seniority proximity, salary / axis fit
- [ ] Verify stage 1 produces explainable shortlist results without per-job LLM calls

---

## 🟠 Short-Term Goals

### 8. Strengthen Matching Explainability and Reliability
- [ ] Add simple explanations for why a job advanced or was rejected
- [ ] Review edge cases for soft vs hard signals, especially seniority for early-career users
- [ ] Validate matching quality on a realistic batch of jobs

### 9. Harden Database and Pipeline Behavior
- [ ] Add indexes for common match filters: `profile_status`, `role_family`, `seniority`, `work_mode`
- [ ] Validate stale-profile behavior and version mismatch handling
- [ ] Add tests for schema/backfill assumptions and profile activation rules

### 10. Testing
- [ ] Unit: schema mapping, extraction transforms, hard filters, deterministic scoring
- [ ] Integration: ingest → extract → user profile build → stage 1 match on SQLite
- [ ] Migration tests: backfill correctness, uniqueness, versioning, stale-profile behavior
- [ ] Edge cases: empty descriptions, duplicate postings, changed content, malformed rows, sparse resumes

### 11. Prepare for Optional Stage 2 Reranking
- [ ] Keep stage 2 separate from stage 1
- [ ] Ensure only shortlist jobs are passed forward
- [ ] Reserve `profile_json` and LLM reasoning for rerank only
- [ ] Define concise rerank output: final score, fit summary, key gaps

---

## ⚪ Defer

- ❌ No cloud deployment yet
- ❌ No vector DB or microservices yet
- ❌ No full multi-source scraping push yet
- ✅ Focus: **finish schema → extraction → user profile → stage 1 first**

---

## 🧠 Principles
**Matching is the product · extract once, match many · denormalize for speed · KISS**

## ✅ Definition of Done (current phase)
- [ ] `job_profile.py` matches the new `job_profiles` table
- [ ] Job extraction fills the new schema correctly
- [ ] Extraction prompt supports all matching-critical fields
- [ ] `user_profile` schema is updated for direct comparison
- [ ] Resume → `user_profile` extraction works
- [ ] Stage 1 runs end-to-end without per-job LLM calls