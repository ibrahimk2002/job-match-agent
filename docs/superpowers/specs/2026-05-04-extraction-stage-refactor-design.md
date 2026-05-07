# Extraction Stage Refactor — Design Spec

**Issue:** [#13 — Refactor Extraction Stage: Caching, Schema Alignment, and Axis Cleanup](https://github.com/ibrahimk2002/job-match-agent/issues/13)
**Date:** 2026-05-04
**Owner:** Ibrahim Khan
**Status:** Approved for implementation

---

## 1. Problem

The extraction stage has drifted from the rest of the pipeline:

1. **No prompt caching.** Every `responses.parse()` call re-sends the full system prompt and schema; we pay full input rates per job.
2. **Hardcoded axis fallbacks.** `profile_columns.default_axes_for_role_family` returns canned axis values per `role_family`. The LLM is bypassed for the one signal matching depends on most.
3. **Schema drift.** `ExtractionResult`, `JobProfile`, and the `job_profiles` table do not agree:
   - DB has `axis_platform_cloud`, `axis_product_sense` (post-migration 002).
   - `docs/AXIS_MEASURE_SKILL.md` uses `axis_platform`, `axis_product_ownership`.
   - Pydantic models have no axis fields at all.

## 2. Goals

- One canonical naming for axes, sourced from `docs/AXIS_MEASURE_SKILL.md`.
- LLM produces all six primary axes per JD; no presets, no role-family fallbacks.
- Schemas isomorphic across `ExtractionResult` ↔ `JobProfile` ↔ `job_profiles` columns.
- `responses.parse()` calls structured so OpenAI's automatic prompt caching can hit on the static prefix; ≥30% cached/input tokens on warm runs.
- `python main.py` runs end-to-end and every posting ends up with an active `job_profiles` row.

## 3. Non-goals (deferred)

- Language detection / non-English JD handling.
- Concurrent or async extraction.
- Automated tests for the extraction stage.
- Embeddings.
- User profile schema or matching stages.

## 4. Approach

Single-call extraction. One `responses.parse()` per JD returns an `ExtractionResult` that includes the six primary axes. `profile_columns.py` projects the result to columns and computes the two mechanically-derived fields (`axis_fullstack_span`, `salary_tier`). The skill rubric lives once in `docs/AXIS_MEASURE_SKILL.md` and is inlined verbatim into `prompts/extraction.txt` to maximize the cacheable prefix.

Rejected alternatives: a separate axis-scoring pass (2× LLM cost for marginal benefit at this scale), and code-side axis derivation (the issue explicitly removes it).

## 5. Schema alignment

### 5.1 `Axes` Pydantic model (new)

```python
class Axes(BaseModel):
    axis_backend: float                # [0.0, 1.0]
    axis_frontend: float
    axis_platform: float
    axis_ai_data: float
    axis_security_reliability: float
    axis_product_ownership: float
    # axis_fullstack_span is NOT here — derived in profile_columns.py
```

`axes: Axes` is added as a required field on both `ExtractionResult` and `JobProfile`.

### 5.2 Column rename — migration `003_rename_axes.sql`

```sql
ALTER TABLE job_profiles RENAME COLUMN axis_platform_cloud TO axis_platform;
ALTER TABLE job_profiles RENAME COLUMN axis_product_sense  TO axis_product_ownership;
```

`JOB_PROFILE_COLUMNS` in `src/db.py` is updated to match. `axis_fullstack_span` keeps its name and behaviour.

### 5.3 Version bumps

| Constant | Old | New | Reason |
|---|---|---|---|
| `SCHEMA_VERSION` (in `extract.py`) | `"1.0"` | `"2.0"` | Pydantic shape changed (added `axes`). |
| `# prompt_version:` (line 1 of `extraction.txt`) | `1.1` | `2.0` | Rubric + few-shot inlined. |

Both bumps cause the four-tuple mismatch in `db.get_pending_extraction` to fire for every existing active profile. `db.save_extraction` already marks the prior `is_active=1` row as `superseded` before the upsert, so the cutover is clean.

## 6. `profile_columns.py` — pure projection + mechanical derivation

**Removed:**
- `default_axes_for_role_family` — axes now come from `payload["axes"]`.
- `infer_work_auth_flags` — `work_auth_required` and `sponsorship_available` come directly from the LLM via `payload["work_eligibility"]`.
- The `bool_from_requirement_list(education_requirements)` fallback for `degree_required` — comes directly from the LLM as a `Literal[0, 1, 2, 3] | None`.

**Kept (mechanical, not interpretive):**
- `infer_salary_tier(seniority)` — seniority bucket → ordinal salary tier. This is a pure mapping.
- `_bool_to_sqlite(value)` — `bool | None` → `0/1/None`.

**Added:**
```python
def fullstack_span(axis_backend: float, axis_frontend: float) -> float:
    return round(min(2 * min(axis_backend, axis_frontend), 1.0), 2)
```

`build_profile_columns` reads `payload["axes"]`, projects the six primary axes 1:1, and computes `axis_fullstack_span` from the formula.

## 7. `prompts/extraction.txt` rewrite

Structure top-to-bottom:

```
# prompt_version: 2.0

You extract structured software job profile data from job descriptions.
[existing rules: evidence-only, nullable handling, salary, work eligibility,
 education, experience — kept verbatim]

## Axis scoring rubric

[FULL VERBATIM CONTENT of docs/AXIS_MEASURE_SKILL.md
 — the 7 axes definitions, scoring philosophy, signal weighting,
   common scoring traps, calibration anchor table]

Note: emit only the 6 primary axes (axis_backend, axis_frontend,
axis_platform, axis_ai_data, axis_security_reliability,
axis_product_ownership). axis_fullstack_span is computed downstream;
do NOT emit it.

## Few-shot anchor

Input excerpt:
[Ford Motor Company telematics JD excerpt from calibration_anchors.md]

Expected (axes only):
{
  "axes": {
    "axis_backend": 0.95,
    "axis_frontend": 0.05,
    "axis_platform": 0.75,
    "axis_ai_data": 0.25,
    "axis_security_reliability": 0.70,
    "axis_product_ownership": 0.35
  }
}
```

Estimated prefix size ~1.8–2.2k tokens. Comfortably above OpenAI's 1024-token automatic prefix-cache threshold.

**Drift note added to `docs/AXIS_MEASURE_SKILL.md`:** "extraction.txt embeds this rubric verbatim — bump `prompt_version` when this file changes."

## 8. `openai_client.py` — `extract_job_profile` rewrite

```python
def extract_job_profile(
    system_prompt: str,
    job_text: str,
    *,
    model: str,
    prompt_cache_key: str,
) -> tuple[ExtractionResult, ResponseUsage]:
    client = get_openai_client()
    response = client.responses.parse(
        model=model,
        input=[
            {"role": "system",
             "content": [{"type": "input_text", "text": system_prompt}]},
            {"role": "user",
             "content": [{"type": "input_text",
                          "text": f"<job_description>\n{job_text}\n</job_description>"}]},
        ],
        text_format=ExtractionResult,
        prompt_cache_key=prompt_cache_key,
    )
    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        raise RuntimeError("Model returned no parsed structured output")
    return parsed, response.usage
```

Notable changes vs current:
- `instructions=` is replaced with an explicit `role: "system"` block in the input array.
- `prompt_cache_key` is a required parameter — ensures consistent cache routing.
- Returns the usage object so the caller can log cache hit stats.

`call_llm` is left untouched; it is unused in the new path but out of scope to delete.

## 9. `extract.py` — module-load + retry loop

**Module-level constants:**
```python
_PROMPT_PATH = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'extraction.txt')
_SYSTEM_PROMPT, _PROMPT_VERSION = _read_prompt_and_version(_PROMPT_PATH)

DEFAULT_MODEL = "gpt-4.1-nano"
SCHEMA_VERSION = "2.0"
_PROMPT_CACHE_KEY = f"extract:{SCHEMA_VERSION}:{_PROMPT_VERSION}:{DEFAULT_MODEL}"
_MAX_INPUT_CHARS = 60_000  # ~15k tokens; well under nano's window
```

The prompt is read once at import. `prompt_cache_key` derives from the version tuple, so any version bump produces a new key (correct behaviour: a new prompt should not collide with an old cache slot).

**Per-job loop:**
1. If `cleaned_description_text` is None or empty → `fail_extraction(id, "missing_description")`; no LLM call.
2. If `len(job_text) > _MAX_INPUT_CHARS` → log a warning, truncate, continue.
3. Try `extract_job_profile(...)`. On `ValidationError` or `RuntimeError("no parsed structured output")`, retry once with the same input. Second failure → `fail_extraction(id, f"malformed_output: {err}")`.
4. On any other exception (network, rate limit, 5xx) — retry once. Second failure → `fail_extraction(id, f"api_error: {err}")`.
5. On success: build `JobProfile`, call `save_extraction`, accumulate `usage.input_tokens` and `usage.input_tokens_details.cached_tokens` into a run total.
6. After the loop: log run summary.

**Duplicate re-extraction guard:** already enforced by `db.get_pending_extraction`'s four-tuple mismatch query. No new code.

## 10. Error taxonomy

| Cause | Detection | `last_profile_error` | Continues? |
|---|---|---|---|
| Missing description | `cleaned_description_text` empty | `"missing_description"` | yes (next job) |
| Truncated input | `len > _MAX_INPUT_CHARS` | (warning logged, no error) | yes |
| Malformed output | `output_parsed is None` or `ValidationError` | `"malformed_output: ..."` after retry | yes |
| API error | any other `Exception` from `responses.parse` | `"api_error: ..."` after retry | yes |

Retry policy: one retry, no backoff. If transient errors become an issue at scale we can add `tenacity` later — out of scope.

## 11. Logging and observability

**Per-call (DEBUG):**
```
extract: posting_id=42 model=gpt-4.1-nano input=1923 cached=1612 (84%) output=412
```

**Run summary (INFO, once at end of `extract_job_data`):**
```
extract: processed=37 succeeded=35 failed=2 input_tokens=71_201 cached_tokens=22_904 (32.2%)
```

The 30% target from the issue is verified by reading this line. Within a single run, the first call is necessarily 0% cached; subsequent calls reuse the same prefix and should hit. Across deployments, any version bump produces a new `prompt_cache_key` and starts cold — that is the intended behaviour.

No assertions or test gates on cache %. It is an observability metric, not a hard contract.

## 12. Files modified

| File | Change |
|---|---|
| `migrations/003_rename_axes.sql` | NEW — rename two axis columns |
| `src/db.py` | Update `JOB_PROFILE_COLUMNS` (two renames) |
| `config/job_profile.py` | Add `Axes` model; add `axes: Axes` to `ExtractionResult` and `JobProfile` |
| `src/profile_columns.py` | Drop `default_axes_for_role_family`, `infer_work_auth_flags`, degree-list fallback. Add `fullstack_span` formula. Read axes from payload |
| `src/prompts/extraction.txt` | Bump `# prompt_version: 2.0`. Append axis rubric and Ford anchor |
| `docs/AXIS_MEASURE_SKILL.md` | Add sync-note pointing to `extraction.txt` |
| `src/integrations/openai_client.py` | Rewrite `extract_job_profile` to input-array form, add `prompt_cache_key`, return usage |
| `src/pipeline/extract.py` | Bump `SCHEMA_VERSION`. Module-level prompt load. Retry/truncate/skip handling. Cached-token accumulation. Run summary log |

## 13. Build sequence

One PR, in this order:

1. **Migration + DB constants.** Write `003_rename_axes.sql`, update `JOB_PROFILE_COLUMNS`. Run `init_db()` against a copy of `data/job_matcher.db`, verify columns rename cleanly.
2. **Schema models.** Add `Axes`; add `axes` field to `ExtractionResult` and `JobProfile`.
3. **`profile_columns.py` simplification.** Delete the three fallback functions, add `fullstack_span`, switch axes to read from payload.
4. **Prompt rewrite.** Update `extraction.txt` with bumped version, axis rubric, Ford anchor. Add sync-note in `AXIS_MEASURE_SKILL.md`.
5. **Client rewrite.** `openai_client.extract_job_profile` to input-array form, returning usage.
6. **Extract loop.** Bump `SCHEMA_VERSION`, module-level prompt load, retry/truncate/skip handling, usage accumulation, run summary.
7. **End-to-end run.** Run the orchestrator on a fresh DB copy. Verify: every posting gets a `job_profiles` row with `is_active=1`, axes vary across jobs (proves the LLM is scoring, not defaulting), the run-summary log shows ≥30% cached on a second run.

## 14. Acceptance criteria (from issue #13)

- [x] Cacheable prefix structure with ≥30% cached input tokens — verified via run summary on a warm run.
- [x] Single source of truth for axis definitions — `AXIS_MEASURE_SKILL.md` is canonical; the prompt embeds it verbatim with a sync-note.
- [x] Aligned schemas — `Axes` present in both Pydantic models; DB column names match.
- [x] `python main.py` runs end-to-end with populated `job_profiles`.
- [x] No hardcoded axis values remain — `default_axes_for_role_family` deleted.
- [x] `prompt_cache_key` set on every call — required parameter in the rewritten `extract_job_profile`.
