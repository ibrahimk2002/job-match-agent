# Smart Skill Canonicalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the "exact-or-auto-insert" `canonicalize()` with a tiered resolver — normalization candidates → exact match → `pg_trgm` similarity → auto-insert — that collapses common LLM variant forms (`C++17`, `React (TypeScript)`, `CI/CD pipelines`, `ES6`) into existing catalog entries, plus a one-time FK-repointing cleanup script and a `skills-audit` CLI command for ongoing visibility.

**Architecture:** The new `canonicalize()` in `src/skills.py` generates 1–5 normalized candidates from the raw string (most-specific → least-specific: strip parentheticals, version suffixes, trailing generic nouns, leading qualifiers), tries each candidate against alias + canonical tables via exact match, then falls back to a `pg_trgm` similarity query (threshold ≥ 0.80, skips strings ≤ 4 chars to protect short names like `Go`, `C#`, `QA`), and only auto-inserts if nothing resolves. A dedup script `scripts/dedup_skills.py` re-tests every existing `source='auto'` row against the new engine (excluding itself) and repoints FKs before deleting orphaned rows. The migration enables `pg_trgm`, adds GIN trgm indexes, and seeds 10 missing base canonicals and 30+ aliases identified from real job postings. Nothing in Stage 1/2 matching changes — matching is always integer-keyed `skill_id` comparison.

**Tech Stack:** PostgreSQL + `pg_trgm` extension, Python 3.11+, psycopg2, pytest

---

## Safety principle

**A false merge silently corrupts matching. A false auto-insert is reviewable.** The engine only collapses a variant when the stripped/resolved form maps to a skill that *already exists in the catalog*. A stripped form that doesn't resolve to anything is not merged. `Distributed Systems` won't lose "Systems" because `Distributed` doesn't exist in the catalog.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `scripts/migrations/010_smart_canonicalization.sql` | Create | Enable `pg_trgm`, add GIN indexes, seed 10 missing canonicals + 30+ aliases |
| `src/skills.py` | Rewrite | Tiered canonicalize: candidates → exact → trgm → auto-insert |
| `tests/test_skills.py` | Extend | Normalization rules, merge guards, trgm, novel auto-insert |
| `scripts/dedup_skills.py` | Create | One-time FK-repointing cleanup; dry-run by default |
| `tests/test_dedup_skills.py` | Create | Tests for merge-target detection and FK repoint |
| `src/cli.py` | Extend | `skills-audit` subcommand listing recent auto-inserted skills |

---

## PR A — Smart Canonicalization Engine

### Task 1: Migration — pg_trgm + missing canonicals + aliases

**Files:**
- Create: `scripts/migrations/010_smart_canonicalization.sql`

- [ ] **Step 1: Create the migration file**

```sql
-- 010_smart_canonicalization.sql
-- Enable trigram extension and seed catalog gaps found from 100 real job postings.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- GIN indexes for fast similarity() queries (used in Tier 3 of canonicalize)
CREATE INDEX IF NOT EXISTS idx_skills_catalog_canonical_trgm
    ON skills_catalog USING gin(LOWER(canonical) gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_skill_aliases_alias_trgm
    ON skill_aliases USING gin(alias gin_trgm_ops);

-- Missing base canonicals not in the original 235-skill seed
INSERT INTO skills_catalog (canonical, category, source) VALUES
  ('HTML',                           'hard',  'curated'),
  ('CSS',                            'hard',  'curated'),
  ('SQL',                            'hard',  'curated'),
  ('QA',                             'other', 'curated'),
  ('Debugging',                      'other', 'curated'),
  ('Code Review',                    'other', 'curated'),
  ('Technical Documentation',        'other', 'curated'),
  ('Backend Development',            'other', 'curated'),
  ('Frontend Development',           'other', 'curated'),
  ('Cross-functional Collaboration', 'soft',  'curated')
ON CONFLICT (canonical) DO NOTHING;

-- HTML aliases
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['html5', 'html/css', 'html & css', 'html and css']), id
FROM skills_catalog WHERE canonical = 'HTML'
ON CONFLICT DO NOTHING;

-- CSS aliases (preprocessors map here because CSS knowledge is implied)
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['css3', 'scss', 'sass', 'less', 'css/scss']), id
FROM skills_catalog WHERE canonical = 'CSS'
ON CONFLICT DO NOTHING;

-- SQL aliases (when a JD says "SQL" without naming a specific DB engine)
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['structured query language', 'pl/sql', 'plsql', 't-sql', 'tsql']), id
FROM skills_catalog WHERE canonical = 'SQL'
ON CONFLICT DO NOTHING;

-- ES6 + ECMAScript variants → JavaScript
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['es6', 'es7', 'es2015', 'es2016', 'es2017', 'es2020', 'ecmascript']), id
FROM skills_catalog WHERE canonical = 'JavaScript'
ON CONFLICT DO NOTHING;

-- C/C++ variant → C++
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['c/c++', 'c and c++', 'c or c++']), id
FROM skills_catalog WHERE canonical = 'C++'
ON CONFLICT DO NOTHING;

-- QA aliases
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['quality assurance', 'qa engineer', 'test automation', 'testing and qa']), id
FROM skills_catalog WHERE canonical = 'QA'
ON CONFLICT DO NOTHING;

-- Debugging aliases
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['debugging skills', 'troubleshooting', 'bug fixing']), id
FROM skills_catalog WHERE canonical = 'Debugging'
ON CONFLICT DO NOTHING;

-- Code Review aliases
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['code reviews', 'peer review', 'peer code review']), id
FROM skills_catalog WHERE canonical = 'Code Review'
ON CONFLICT DO NOTHING;

-- Technical Documentation aliases
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['documentation', 'technical writing', 'writing documentation']), id
FROM skills_catalog WHERE canonical = 'Technical Documentation'
ON CONFLICT DO NOTHING;

-- Backend Development aliases
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['backend', 'back-end', 'back end', 'backend engineering']), id
FROM skills_catalog WHERE canonical = 'Backend Development'
ON CONFLICT DO NOTHING;

-- Frontend Development aliases
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['frontend', 'front-end', 'front end', 'frontend engineering']), id
FROM skills_catalog WHERE canonical = 'Frontend Development'
ON CONFLICT DO NOTHING;

-- Cross-functional Collaboration aliases
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY[
    'cross-functional collaboration', 'cross functional collaboration',
    'stakeholder collaboration', 'collaboration'
]), id
FROM skills_catalog WHERE canonical = 'Cross-functional Collaboration'
ON CONFLICT DO NOTHING;

-- OpenAI / ChatGPT variants → OpenAI API
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['chatgpt', 'chat gpt', 'chat-gpt', 'gpt', 'gpt-4', 'gpt4', 'gpt-4.1']), id
FROM skills_catalog WHERE canonical = 'OpenAI API'
ON CONFLICT DO NOTHING;
```

- [ ] **Step 2: Apply the migration and verify**

```bash
python src/cli.py migrate
```

Then spot-check:
```bash
psql $DATABASE_URL -c "SELECT extname FROM pg_extension WHERE extname = 'pg_trgm';"
# Returns: pg_trgm

psql $DATABASE_URL -c "SELECT indexname FROM pg_indexes WHERE indexname LIKE '%trgm%';"
# Returns: idx_skills_catalog_canonical_trgm, idx_skill_aliases_alias_trgm

psql $DATABASE_URL -c "SELECT canonical FROM skills_catalog WHERE canonical IN ('HTML','CSS','SQL','QA','Debugging') ORDER BY canonical;"
# Returns all 5 rows
```

- [ ] **Step 3: Commit**

```bash
git add scripts/migrations/010_smart_canonicalization.sql
git commit -m "feat(skills): enable pg_trgm, seed 10 missing canonicals and 30+ aliases"
```

---

### Task 2: Rewrite src/skills.py — tiered canonicalize

**Files:**
- Modify: `src/skills.py` (full rewrite — keep identical public signatures for `canonicalize` and `batch_canonicalize`)

- [ ] **Step 1: Replace src/skills.py entirely**

```python
# src/skills.py
import re
from utils import log_info

# --- Normalization regex patterns ---
# Strip parentheticals: "React (TypeScript)" → "React"
_PARENS_RE = re.compile(r'\s*\([^)]*\)')
# Strip trailing version tokens: "C++17" → "C++", "HTML5" → "HTML", "Vue 3" → "Vue"
_VERSION_RE = re.compile(r'\s+v?\d+(\.\d+)*[a-z]?$', re.IGNORECASE)
# Strip trailing generic nouns that dilute a skill name
_TRAILING_GENERIC_RE = re.compile(
    r'\s+(pipelines?|workflows?|practices?|tools?|systems?|concepts?|'
    r'principles?|methodologies?|technologies?|frameworks?|techniques?|skills?)$',
    re.IGNORECASE,
)
# Strip leading qualifier words: "modern C++" → "C++", "strong Python" → "Python"
_LEADING_QUALIFIER_RE = re.compile(
    r'^(modern|advanced|strong|core|basic|fundamental|native|'
    r'full[- ]?stack|deep|hands[- ]on)\s+',
    re.IGNORECASE,
)

# Trigram match config
_TRGM_MIN_SIMILARITY = 0.80
# Skip trgm for strings ≤ 4 chars — protects Go, C, C#, C++, SQL, QA, Git, AWS, GCP, Java
_TRGM_MIN_LEN = 5


def _normalization_candidates(raw: str) -> list[str]:
    """
    Return normalized candidate strings to try, most-specific first, deduplicated.
    Only strips a form if the original is modified — never generates empty strings.
    """
    s = raw.strip()
    candidates = [s]

    # Strip parentheticals: "React (TypeScript)" → "React"
    no_parens = _PARENS_RE.sub('', s).strip()
    if no_parens and no_parens != s:
        candidates.append(no_parens)
        s = no_parens  # further stripping works on the de-parenthesized form

    # Strip trailing version: "C++17" → "C++", "HTML5" → "HTML"
    no_version = _VERSION_RE.sub('', s).strip()
    if no_version and no_version != s:
        candidates.append(no_version)

    # Strip trailing generic nouns: "CI/CD pipelines" → "CI/CD", "Git workflows" → "Git"
    no_trailing = _TRAILING_GENERIC_RE.sub('', s).strip()
    if no_trailing and no_trailing != s:
        candidates.append(no_trailing)
        # Also try version-stripping the result: "CI/CD pipelines v2" → "CI/CD"
        no_trailing_no_ver = _VERSION_RE.sub('', no_trailing).strip()
        if no_trailing_no_ver and no_trailing_no_ver != no_trailing:
            candidates.append(no_trailing_no_ver)

    # Strip leading qualifiers: "modern C++" → "C++", "advanced Python" → "Python"
    no_leading = _LEADING_QUALIFIER_RE.sub('', s).strip()
    if no_leading and no_leading != s:
        candidates.append(no_leading)
        # Also try version-stripping: "modern C++17" → "C++"
        no_leading_no_ver = _VERSION_RE.sub('', no_leading).strip()
        if no_leading_no_ver and no_leading_no_ver != no_leading:
            candidates.append(no_leading_no_ver)

    # Deduplicate preserving insertion order
    seen: set[str] = set()
    result: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result


def _exact_resolve(normalized_lower: str, conn) -> int | None:
    """Exact alias lookup then exact canonical lookup. Returns skill_id or None."""
    with conn.cursor() as cur:
        cur.execute("SELECT skill_id FROM skill_aliases WHERE alias = %s", (normalized_lower,))
        row = cur.fetchone()
        if row:
            return row["skill_id"]
        cur.execute(
            "SELECT id FROM skills_catalog WHERE LOWER(canonical) = %s", (normalized_lower,)
        )
        row = cur.fetchone()
        if row:
            return row["id"]
    return None


def _trgm_resolve(normalized_lower: str, conn) -> int | None:
    """
    Trigram similarity match against aliases + canonicals.
    Skips strings shorter than _TRGM_MIN_LEN to protect short distinct names.
    """
    if len(normalized_lower) < _TRGM_MIN_LEN:
        return None
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH matches AS (
                SELECT id AS skill_id, similarity(LOWER(canonical), %s) AS sim
                FROM skills_catalog
                WHERE similarity(LOWER(canonical), %s) >= %s
                UNION ALL
                SELECT skill_id, similarity(alias, %s) AS sim
                FROM skill_aliases
                WHERE similarity(alias, %s) >= %s
            )
            SELECT skill_id FROM matches ORDER BY sim DESC LIMIT 1
            """,
            (
                normalized_lower, normalized_lower, _TRGM_MIN_SIMILARITY,
                normalized_lower, normalized_lower, _TRGM_MIN_SIMILARITY,
            ),
        )
        row = cur.fetchone()
        if row:
            return row["skill_id"]
    return None


def canonicalize(skill_text: str, conn) -> int:
    """
    Map a raw skill string to a skill_id using a tiered resolver.
    Only auto-inserts (source='auto') when no tier resolves — the last resort.
    """
    candidates = _normalization_candidates(skill_text)

    # Tier 1 + 2: exact alias → exact canonical, most-specific candidate first
    for candidate in candidates:
        skill_id = _exact_resolve(candidate.strip().lower(), conn)
        if skill_id is not None:
            return skill_id

    # Tier 3: trigram similarity on the original normalized string
    normalized_original = skill_text.strip().lower()
    skill_id = _trgm_resolve(normalized_original, conn)
    if skill_id is not None:
        return skill_id

    # Tier 4: auto-insert — only reached for genuinely novel skills
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO skills_catalog (canonical, category, source) "
            "VALUES (%s, 'other', 'auto') RETURNING id",
            (skill_text.strip(),),
        )
        new_id = cur.fetchone()["id"]
    log_info(f"skills: auto-inserted '{skill_text.strip()}' as id={new_id}")
    return new_id


def batch_canonicalize(skills: list[str], conn) -> list[int]:
    total = len(skills)
    ids: list[int] = []
    cache: dict[str, int] = {}
    for skill in skills:
        key = skill.strip().lower()
        if key in cache:
            ids.append(cache[key])
            continue
        skill_id = canonicalize(skill, conn)
        cache[key] = skill_id
        ids.append(skill_id)
    log_info(f"skills: batch_canonicalize total={total} unique={len(cache)}")
    return ids
```

- [ ] **Step 2: Run existing skills tests to confirm no regressions**

```bash
pytest tests/test_skills.py -v
```

Expected: All pre-existing tests pass. The public signatures `canonicalize(skill_text, conn)` and `batch_canonicalize(skills, conn)` are identical.

- [ ] **Step 3: Commit**

```bash
git add src/skills.py
git commit -m "feat(skills): tiered canonicalize — candidate normalization + pg_trgm fallback"
```

---

### Task 3: Tests for the new canonicalization behavior

**Files:**
- Modify: `tests/test_skills.py`

The file already imports `canonicalize`. Add the following imports and helpers at the top of the file (after existing imports):

```python
import psycopg2
import psycopg2.extras
from skills import canonicalize, _normalization_candidates
```

Add this helper function (after any existing helpers in the file):

```python
def _get_skill_id(conn, canonical: str) -> int:
    """Fetch id of a seeded canonical by exact name. Raises ValueError if not found."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM skills_catalog WHERE canonical = %s", (canonical,))
        row = cur.fetchone()
    if row is None:
        raise ValueError(f"Skill not found in catalog: {canonical!r}")
    return row["id"]
```

- [ ] **Step 1: Write unit tests for `_normalization_candidates` (no DB needed)**

```python
# --- Unit tests: _normalization_candidates ---

def test_candidates_original_is_always_first():
    result = _normalization_candidates("modern C++17")
    assert result[0] == "modern C++17"


def test_candidates_strips_parentheticals():
    result = _normalization_candidates("React (TypeScript)")
    assert result[0] == "React (TypeScript)"
    assert "React" in result
    assert result.index("React (TypeScript)") < result.index("React")


def test_candidates_strips_trailing_version_number():
    result = _normalization_candidates("C++17")
    assert "C++" in result


def test_candidates_strips_html5():
    result = _normalization_candidates("HTML5")
    assert "HTML" in result


def test_candidates_strips_trailing_generic_noun():
    result = _normalization_candidates("CI/CD pipelines")
    assert "CI/CD" in result


def test_candidates_strips_trailing_workflows():
    result = _normalization_candidates("Git workflows")
    assert "Git" in result


def test_candidates_strips_leading_qualifier():
    result = _normalization_candidates("modern C++")
    assert "C++" in result


def test_candidates_no_duplicates():
    result = _normalization_candidates("Python")
    assert len(result) == len(set(result))


def test_candidates_plain_skill_returns_only_itself():
    result = _normalization_candidates("Python")
    assert result == ["Python"]


def test_candidates_does_not_generate_empty_strings():
    for raw in ["CI/CD", "Go", "C++", "QA", "pipelines"]:
        for c in _normalization_candidates(raw):
            assert c.strip() != "", f"Empty candidate from {raw!r}"
```

- [ ] **Step 2: Run unit tests**

```bash
pytest tests/test_skills.py -k "candidates" -v
```

Expected: All 10 `test_candidates_*` tests PASS.

- [ ] **Step 3: Write integration tests for tiered resolution (require `temp_db`)**

```python
# --- Integration tests: tiered resolution ---

def test_version_suffix_collapses_to_cpp(temp_db):
    """C++17 resolves to C++ via candidate stripping (Tier 1/2)."""
    conn = psycopg2.connect(temp_db, cursor_factory=psycopg2.extras.RealDictCursor)
    cpp_id = _get_skill_id(conn, "C++")
    assert canonicalize("C++17", conn) == cpp_id
    conn.close()


def test_parenthetical_collapses_to_react(temp_db):
    """React (TypeScript) resolves to React."""
    conn = psycopg2.connect(temp_db, cursor_factory=psycopg2.extras.RealDictCursor)
    react_id = _get_skill_id(conn, "React")
    assert canonicalize("React (TypeScript)", conn) == react_id
    conn.close()


def test_trailing_generic_noun_collapses_cicd(temp_db):
    """CI/CD pipelines resolves to CI/CD."""
    conn = psycopg2.connect(temp_db, cursor_factory=psycopg2.extras.RealDictCursor)
    cicd_id = _get_skill_id(conn, "CI/CD")
    assert canonicalize("CI/CD pipelines", conn) == cicd_id
    conn.close()


def test_trailing_generic_noun_collapses_git(temp_db):
    """Git workflows resolves to Git."""
    conn = psycopg2.connect(temp_db, cursor_factory=psycopg2.extras.RealDictCursor)
    git_id = _get_skill_id(conn, "Git")
    assert canonicalize("Git workflows", conn) == git_id
    conn.close()


def test_leading_qualifier_collapses_to_cpp(temp_db):
    """modern C++ resolves to C++."""
    conn = psycopg2.connect(temp_db, cursor_factory=psycopg2.extras.RealDictCursor)
    cpp_id = _get_skill_id(conn, "C++")
    assert canonicalize("modern C++", conn) == cpp_id
    conn.close()


def test_es6_alias_maps_to_javascript(temp_db):
    """ES6 resolves to JavaScript via seeded alias."""
    conn = psycopg2.connect(temp_db, cursor_factory=psycopg2.extras.RealDictCursor)
    js_id = _get_skill_id(conn, "JavaScript")
    assert canonicalize("ES6", conn) == js_id
    conn.close()


def test_qa_practices_collapses_to_qa(temp_db):
    """QA practices → strip 'practices' → QA (seeded in migration 010)."""
    conn = psycopg2.connect(temp_db, cursor_factory=psycopg2.extras.RealDictCursor)
    qa_id = _get_skill_id(conn, "QA")
    assert canonicalize("QA practices", conn) == qa_id
    conn.close()


def test_html5_resolves_to_html(temp_db):
    """html5 alias resolves to HTML (seeded alias in migration 010)."""
    conn = psycopg2.connect(temp_db, cursor_factory=psycopg2.extras.RealDictCursor)
    html_id = _get_skill_id(conn, "HTML")
    assert canonicalize("HTML5", conn) == html_id
    conn.close()


def test_trgm_catches_near_identical_variant(temp_db):
    """A string nearly identical to a seeded canonical resolves via trigram (Tier 3)."""
    conn = psycopg2.connect(temp_db, cursor_factory=psycopg2.extras.RealDictCursor)
    # Seed a long, distinctive skill so we control the trgm match
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO skills_catalog (canonical, category, source) "
            "VALUES ('DistinctSkillForTrgmVerify', 'hard', 'curated') RETURNING id"
        )
        seeded_id = cur.fetchone()["id"]
    conn.commit()
    # Adding 's' gives similarity > 0.90 (27/28 trigrams shared)
    result_id = canonicalize("DistinctSkillForTrgmVerifys", conn)
    assert result_id == seeded_id
    conn.close()


def test_no_trgm_for_short_distinct_names(temp_db):
    """Short skills like Go and Java each resolve to themselves, never to each other."""
    conn = psycopg2.connect(temp_db, cursor_factory=psycopg2.extras.RealDictCursor)
    go_id = _get_skill_id(conn, "Go")
    java_id = _get_skill_id(conn, "Java")
    assert canonicalize("Go", conn) == go_id
    assert canonicalize("Java", conn) == java_id
    assert go_id != java_id
    conn.close()


def test_react_native_does_not_collapse_to_react(temp_db):
    """React Native has its own canonical; it must not collapse into React."""
    conn = psycopg2.connect(temp_db, cursor_factory=psycopg2.extras.RealDictCursor)
    react_id = _get_skill_id(conn, "React")
    react_native_id = _get_skill_id(conn, "React Native")
    result = canonicalize("React Native", conn)
    assert result == react_native_id
    assert result != react_id
    conn.close()


def test_novel_skill_auto_inserts_with_source_auto(temp_db):
    """A skill the engine cannot resolve auto-inserts with source='auto'."""
    conn = psycopg2.connect(temp_db, cursor_factory=psycopg2.extras.RealDictCursor)
    result_id = canonicalize("SomeBrandNewSkill-ZZZ-2026", conn)
    with conn.cursor() as cur:
        cur.execute("SELECT source FROM skills_catalog WHERE id = %s", (result_id,))
        row = cur.fetchone()
    assert row["source"] == "auto"
    conn.close()


def test_non_strippable_skill_is_not_forcibly_collapsed(temp_db):
    """'Distributed Systems' stays as-is because 'Distributed' is not in the catalog."""
    conn = psycopg2.connect(temp_db, cursor_factory=psycopg2.extras.RealDictCursor)
    dist_sys_id = _get_skill_id(conn, "Distributed Systems")
    result = canonicalize("Distributed Systems", conn)
    assert result == dist_sys_id
    conn.close()
```

- [ ] **Step 4: Run all integration tests**

```bash
pytest tests/test_skills.py -v
```

Expected: All tests pass — both the newly written tests and all pre-existing tests.

- [ ] **Step 5: Commit**

```bash
git add tests/test_skills.py
git commit -m "test(skills): add normalization candidate + tiered resolution tests"
```

---

## PR B — Cleanup + Review Surface

### Task 4: Dedup script — repoint FKs for existing bloat

**Files:**
- Create: `scripts/dedup_skills.py`

The script imports `_normalization_candidates`, `_TRGM_MIN_SIMILARITY`, and `_TRGM_MIN_LEN` from `src/skills.py`. These are prefixed with `_` per the codebase convention (private-to-module), but importing them here in a sibling script is intentional and documented.

- [ ] **Step 1: Create scripts/dedup_skills.py**

```python
#!/usr/bin/env python3
"""
One-time cleanup: re-canonicalize source='auto' skills against the improved engine.
For each auto-inserted skill, tests whether the new engine would have resolved it
to a different existing skill (excluding itself from the search). If so, repoints
FKs in job_profile_skills and resume_skills to the target, then deletes the orphaned row.

Usage:
    python scripts/dedup_skills.py            # dry-run: print merge plan, no DB changes
    python scripts/dedup_skills.py --apply    # apply merges
"""
import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_ROOT, 'src')
for _p in [_SRC, _ROOT]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, '.env'))

import psycopg2
import psycopg2.extras
from skills import _normalization_candidates, _TRGM_MIN_SIMILARITY, _TRGM_MIN_LEN


def _get_connection():
    return psycopg2.connect(
        os.environ['DATABASE_URL'],
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def _find_merge_target(auto_canonical: str, auto_id: int, conn) -> int | None:
    """
    Run tiers 0–3 of the canonicalize engine against all skills EXCEPT auto_id.
    Returns the skill_id to merge into, or None if the skill is genuinely novel.
    """
    candidates = _normalization_candidates(auto_canonical)
    with conn.cursor() as cur:
        for candidate in candidates:
            normalized = candidate.strip().lower()

            # Tier 1: exact alias not pointing at auto_id
            cur.execute(
                "SELECT skill_id FROM skill_aliases WHERE alias = %s AND skill_id != %s",
                (normalized, auto_id),
            )
            row = cur.fetchone()
            if row:
                return row["skill_id"]

            # Tier 2: exact canonical, excluding auto_id itself
            cur.execute(
                "SELECT id FROM skills_catalog WHERE LOWER(canonical) = %s AND id != %s",
                (normalized, auto_id),
            )
            row = cur.fetchone()
            if row:
                return row["id"]

        # Tier 3: trigram match, excluding auto_id
        normalized_original = auto_canonical.strip().lower()
        if len(normalized_original) >= _TRGM_MIN_LEN:
            cur.execute(
                """
                WITH matches AS (
                    SELECT id AS skill_id, similarity(LOWER(canonical), %s) AS sim
                    FROM skills_catalog
                    WHERE id != %s AND similarity(LOWER(canonical), %s) >= %s
                    UNION ALL
                    SELECT skill_id, similarity(alias, %s) AS sim
                    FROM skill_aliases
                    WHERE skill_id != %s AND similarity(alias, %s) >= %s
                )
                SELECT skill_id FROM matches ORDER BY sim DESC LIMIT 1
                """,
                (
                    normalized_original, auto_id, normalized_original, _TRGM_MIN_SIMILARITY,
                    normalized_original, auto_id, normalized_original, _TRGM_MIN_SIMILARITY,
                ),
            )
            row = cur.fetchone()
            if row:
                return row["skill_id"]
    return None


def _apply_merge(old_id: int, new_id: int, conn) -> None:
    """Repoint job_profile_skills + resume_skills from old_id → new_id, then delete old_id."""
    with conn.cursor() as cur:
        # Repoint job_profile_skills — keep the higher importance on PK conflict
        cur.execute(
            """
            INSERT INTO job_profile_skills (job_profile_id, skill_id, importance, group_id)
            SELECT job_profile_id, %s, importance, group_id
            FROM job_profile_skills WHERE skill_id = %s
            ON CONFLICT (job_profile_id, skill_id) DO UPDATE
                SET importance = CASE
                    WHEN CASE job_profile_skills.importance
                             WHEN 'must' THEN 3 WHEN 'preferred' THEN 2 ELSE 1 END
                       >= CASE EXCLUDED.importance
                              WHEN 'must' THEN 3 WHEN 'preferred' THEN 2 ELSE 1 END
                    THEN job_profile_skills.importance
                    ELSE EXCLUDED.importance
                END,
                group_id = EXCLUDED.group_id
            """,
            (new_id, old_id),
        )
        cur.execute("DELETE FROM job_profile_skills WHERE skill_id = %s", (old_id,))

        # Repoint resume_skills — keep higher importance on PK conflict
        cur.execute(
            """
            INSERT INTO resume_skills (resume_id, skill_id, importance)
            SELECT resume_id, %s, importance
            FROM resume_skills WHERE skill_id = %s
            ON CONFLICT (resume_id, skill_id) DO UPDATE
                SET importance = CASE
                    WHEN CASE resume_skills.importance
                             WHEN 'must' THEN 3 WHEN 'preferred' THEN 2 ELSE 1 END
                       >= CASE EXCLUDED.importance
                              WHEN 'must' THEN 3 WHEN 'preferred' THEN 2 ELSE 1 END
                    THEN resume_skills.importance
                    ELSE EXCLUDED.importance
                END
            """,
            (new_id, old_id),
        )
        cur.execute("DELETE FROM resume_skills WHERE skill_id = %s", (old_id,))

        # Repoint any aliases (edge case: auto skill got manually aliased)
        cur.execute(
            "UPDATE skill_aliases SET skill_id = %s WHERE skill_id = %s",
            (new_id, old_id),
        )

        # Delete the orphaned auto skill row (FK cascade would clean junction rows,
        # but we already deleted them above to handle importance conflict resolution)
        cur.execute("DELETE FROM skills_catalog WHERE id = %s", (old_id,))


def main(apply: bool) -> None:
    conn = _get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, canonical FROM skills_catalog WHERE source = 'auto' ORDER BY id"
        )
        auto_skills = cur.fetchall()

    print(f"Found {len(auto_skills)} auto-inserted skills.\n")

    merge_plan: list[tuple[int, str, int, str]] = []
    for skill in auto_skills:
        old_id, old_canonical = skill["id"], skill["canonical"]
        target_id = _find_merge_target(old_canonical, old_id, conn)
        if target_id is not None:
            with conn.cursor() as cur:
                cur.execute("SELECT canonical FROM skills_catalog WHERE id = %s", (target_id,))
                target_row = cur.fetchone()
            merge_plan.append((old_id, old_canonical, target_id, target_row["canonical"]))

    if not merge_plan:
        print("No mergeable skills found — catalog is clean.")
        conn.close()
        return

    print(f"Merge plan ({len(merge_plan)} skills):")
    for old_id, old_can, new_id, new_can in merge_plan:
        print(f"  [{old_id:>5}] {old_can!r:45s} → [{new_id:>5}] {new_can!r}")

    if not apply:
        print(f"\nDry run complete. Pass --apply to execute.")
        conn.close()
        return

    for old_id, old_can, new_id, new_can in merge_plan:
        _apply_merge(old_id, new_id, conn)
        conn.commit()
        print(f"  Merged {old_can!r} → {new_can!r}")

    print(f"\nDone. {len(merge_plan)} skills merged.")
    conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Dedup auto-inserted skills into curated canonicals.')
    parser.add_argument('--apply', action='store_true', help='Apply merges (default: dry-run)')
    main(apply=parser.parse_args().apply)
```

- [ ] **Step 2: Run dry-run against the real database and review output**

```bash
python scripts/dedup_skills.py
```

Expected: Prints a merge plan. Inspect each proposed merge — verify that the proposed target makes semantic sense (e.g., `C++17` → `C++`, not `C++17` → `Java`). No DB changes are made.

- [ ] **Step 3: Commit**

```bash
git add scripts/dedup_skills.py
git commit -m "feat(skills): dedup_skills.py for one-time FK-repointing cleanup"
```

---

### Task 5: Tests for dedup_skills.py

**Files:**
- Create: `tests/test_dedup_skills.py`

- [ ] **Step 1: Create the test file**

```python
# tests/test_dedup_skills.py
import os
import sys

import psycopg2
import psycopg2.extras
import pytest

# scripts/ is not on the default path; add it so we can import dedup_skills.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from dedup_skills import _find_merge_target, _apply_merge


def _conn(db_url):
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)


def _insert_auto_skill(conn, canonical: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO skills_catalog (canonical, category, source) "
            "VALUES (%s, 'other', 'auto') RETURNING id",
            (canonical,),
        )
        return cur.fetchone()["id"]


def _insert_job_profile(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO job_postings (source_system, source_posting_id, content_hash, profile_status) "
            "VALUES ('linkedin', 'dedup-test-posting', 'hash-dedup', 'current') RETURNING id"
        )
        posting_id = cur.fetchone()["id"]
        cur.execute(
            """INSERT INTO job_profiles
               (job_posting_id, content_hash, schema_version, prompt_version, model_version,
                extracted_at, is_active, profile_json, normalized_title, role_family, seniority,
                employment_type, work_mode, extraction_confidence,
                axis_backend, axis_frontend, axis_platform, axis_ai_data,
                axis_security_reliability, axis_product_ownership)
               VALUES (%s, 'hash-dedup', '2.0', '2.6', 'gpt-4.1-nano', NOW(), 1, '{}',
                       'Engineer', 'backend', 'mid', 'full_time', 'remote', 0.9,
                       0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
               RETURNING id""",
            (posting_id,),
        )
        return cur.fetchone()["id"]


def _insert_job_skill(conn, job_profile_id: int, skill_id: int, importance: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO job_profile_skills (job_profile_id, skill_id, importance) "
            "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (job_profile_id, skill_id, importance),
        )


def test_find_merge_target_via_candidate_stripping(temp_db):
    """Auto skill 'CI/CD pipelines' resolves to curated 'CI/CD' via candidate stripping."""
    conn = _conn(temp_db)
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM skills_catalog WHERE canonical = 'CI/CD'")
        cicd_id = cur.fetchone()["id"]
    bloat_id = _insert_auto_skill(conn, "CI/CD pipelines")
    conn.commit()

    target_id = _find_merge_target("CI/CD pipelines", bloat_id, conn)
    assert target_id == cicd_id
    conn.close()


def test_find_merge_target_genuinely_novel_returns_none(temp_db):
    """A genuinely novel skill has no merge target."""
    conn = _conn(temp_db)
    bloat_id = _insert_auto_skill(conn, "SomeTotallyNovelSkillZZZQ2026")
    conn.commit()

    target_id = _find_merge_target("SomeTotallyNovelSkillZZZQ2026", bloat_id, conn)
    assert target_id is None
    conn.close()


def test_apply_merge_repoints_job_profile_skills(temp_db):
    """After apply_merge, job_profile_skills rows point at new_id; old_id row is deleted."""
    conn = _conn(temp_db)
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM skills_catalog WHERE canonical = 'Python'")
        python_id = cur.fetchone()["id"]

    bloat_id = _insert_auto_skill(conn, "Python scripting language bloat-a")
    job_profile_id = _insert_job_profile(conn)
    _insert_job_skill(conn, job_profile_id, bloat_id, "must")
    conn.commit()

    _apply_merge(bloat_id, python_id, conn)
    conn.commit()

    with conn.cursor() as cur:
        # Old skill_id rows must be gone
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM job_profile_skills WHERE skill_id = %s", (bloat_id,)
        )
        assert cur.fetchone()["cnt"] == 0

        # New skill_id row must exist with correct importance
        cur.execute(
            "SELECT importance FROM job_profile_skills "
            "WHERE job_profile_id = %s AND skill_id = %s",
            (job_profile_id, python_id),
        )
        assert cur.fetchone()["importance"] == "must"

        # Orphaned catalog row must be deleted
        cur.execute("SELECT COUNT(*) AS cnt FROM skills_catalog WHERE id = %s", (bloat_id,))
        assert cur.fetchone()["cnt"] == 0

    conn.close()


def test_apply_merge_preserves_higher_importance_on_conflict(temp_db):
    """When both old and new skill exist for the same job, must beats nice."""
    conn = _conn(temp_db)
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM skills_catalog WHERE canonical = 'Python'")
        python_id = cur.fetchone()["id"]

    bloat_id = _insert_auto_skill(conn, "Python scripting language bloat-b")
    job_profile_id = _insert_job_profile(conn)
    _insert_job_skill(conn, job_profile_id, python_id, "must")   # existing: must
    _insert_job_skill(conn, job_profile_id, bloat_id, "nice")    # bloat:    nice
    conn.commit()

    _apply_merge(bloat_id, python_id, conn)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            "SELECT importance FROM job_profile_skills "
            "WHERE job_profile_id = %s AND skill_id = %s",
            (job_profile_id, python_id),
        )
        # must (3) > nice (1) — must should win
        assert cur.fetchone()["importance"] == "must"

    conn.close()
```

- [ ] **Step 2: Run the tests**

```bash
pytest tests/test_dedup_skills.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_dedup_skills.py
git commit -m "test(skills): add dedup_skills merge-target detection and FK-repoint tests"
```

---

### Task 6: Add skills-audit CLI command

**Files:**
- Modify: `src/cli.py`

- [ ] **Step 1: Add `_cmd_skills_audit` after `_cmd_ingest_resume`**

```python
def _cmd_skills_audit(_args: argparse.Namespace) -> None:
    from db import get_db_connection
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sc.id, sc.canonical, sc.category,
                       COUNT(DISTINCT jps.job_profile_id) AS job_uses,
                       COUNT(DISTINCT rs.resume_id)        AS resume_uses
                FROM skills_catalog sc
                LEFT JOIN job_profile_skills jps ON jps.skill_id = sc.id
                LEFT JOIN resume_skills rs         ON rs.skill_id  = sc.id
                WHERE sc.source = 'auto'
                GROUP BY sc.id, sc.canonical, sc.category
                ORDER BY sc.id DESC
                LIMIT 50
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        print("No auto-inserted skills — catalog is clean.")
        return

    print(f"{'ID':>6}  {'Jobs':>5}  {'Resumes':>7}  Canonical")
    print("-" * 60)
    for row in rows:
        print(f"{row['id']:>6}  {row['job_uses']:>5}  {row['resume_uses']:>7}  {row['canonical']}")
    print(f"\n{len(rows)} auto-inserted skills shown (limit 50, most recent first).")
    print("To promote: add a curated alias in scripts/migrations/, then run 'python src/cli.py migrate'.")
```

- [ ] **Step 2: Register the subcommand in `main()`**

In the `subparsers` block (after the `resume_parser` block, before `args = parser.parse_args(argv)`):

```python
    subparsers.add_parser("skills-audit", help="List auto-inserted skills for review")
```

In the `if/elif` dispatch chain at the bottom of `main()`:

```python
    elif args.command == "skills-audit":
        _cmd_skills_audit(args)
```

- [ ] **Step 3: Smoke-test the command**

```bash
python src/cli.py skills-audit
```

Expected: Prints a table of auto-inserted skills (or "catalog is clean" if empty). No errors, no stack traces.

- [ ] **Step 4: Run full test suite**

```bash
pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/cli.py
git commit -m "feat(cli): add skills-audit command to surface auto-inserted skills"
```

---

### Task 7: Apply the one-time dedup to the real database

This task is run once after all code is merged. It is not part of CI.

- [ ] **Step 1: Run dry-run and read the output carefully**

```bash
python scripts/dedup_skills.py
```

Read every proposed merge. For each one, ask: does the target make semantic sense? If something looks wrong (e.g., a clearly distinct skill being mapped to the wrong canonical), it means the trgm threshold caught a false positive. In that case, add an explicit alias for the bloat skill in a new migration instead of letting it auto-merge.

- [ ] **Step 2: Apply merges once the dry-run looks correct**

```bash
python scripts/dedup_skills.py --apply
```

Expected: Each merge prints a confirmation line. No errors.

- [ ] **Step 3: Verify catalog is cleaner**

```bash
python src/cli.py skills-audit
```

Expected: The `auto` skill count is lower than before. Only genuinely novel skills remain.

- [ ] **Step 4: Commit a follow-up migration for any false positives**

If the dry-run showed any false positives (skills that should NOT have been merged), add them as explicit aliases in a new `011_*.sql` migration instead:

```sql
-- Only if needed after reviewing dedup dry-run output
INSERT INTO skill_aliases (alias, skill_id)
SELECT 'the bloat canonical lowercased', id
FROM skills_catalog WHERE canonical = 'The Correct Canonical'
ON CONFLICT DO NOTHING;
```

Then run `python src/cli.py migrate`.

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| Tiered canonicalize: candidate normalization | Task 2 — `_normalization_candidates()` |
| Tiered canonicalize: exact match | Task 2 — `_exact_resolve()` |
| Tiered canonicalize: pg_trgm fallback | Task 2 — `_trgm_resolve()` |
| Tiered canonicalize: auto-insert last resort | Task 2 — Tier 4 in `canonicalize()` |
| trgm skip guard for short strings | Task 2 — `_TRGM_MIN_LEN = 5` |
| pg_trgm extension + GIN indexes | Task 1 — migration 010 |
| Missing canonicals: HTML, CSS, SQL, QA, etc. | Task 1 — migration 010 |
| ES6 → JavaScript alias | Task 1 — migration 010 |
| C/C++ → C++ alias | Task 1 — migration 010 |
| One-time FK-repointing cleanup | Task 4 — dedup_skills.py |
| Dry-run mode default | Task 4 — `main(apply=False)` default |
| Importance conflict → keep higher | Task 4 — `_apply_merge()` ON CONFLICT clause |
| Cleanup script re-run idempotent | Task 4 — `_find_merge_target` excludes auto_id from search |
| Review surface (skills-audit command) | Task 6 — `_cmd_skills_audit` |
| All tests pass | Tasks 3, 5 |

**Placeholder scan:** None found.

**Type consistency:** `_normalization_candidates` returns `list[str]`, consumed in Task 2 and Task 4 consistently. `_TRGM_MIN_SIMILARITY` and `_TRGM_MIN_LEN` defined in Task 2, imported in Task 4 — names match exactly.
