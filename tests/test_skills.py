import psycopg2
import psycopg2.extras
import pytest

from skills import canonicalize, batch_canonicalize


def _conn(db_url):
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)


def _seed_one(conn, canonical, category="hard", aliases=None):
    """Insert one skill + optional aliases. Commits.

    Uses ON CONFLICT DO NOTHING so tests work even when the migration has
    already seeded the same canonical name into the catalog.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO skills_catalog (canonical, category, source)
            VALUES (%s, %s, 'curated')
            ON CONFLICT (canonical) DO UPDATE SET canonical = EXCLUDED.canonical
            RETURNING id
            """,
            (canonical, category),
        )
        skill_id = cur.fetchone()["id"]
        for alias in (aliases or []):
            cur.execute(
                "INSERT INTO skill_aliases (alias, skill_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (alias.lower(), skill_id),
            )
    conn.commit()
    return skill_id


def test_known_alias_resolves(temp_db):
    conn = _conn(temp_db)
    seed_id = _seed_one(conn, "Python", aliases=["python3", "py"])
    result = canonicalize("python3", conn)
    assert result == seed_id
    conn.close()


def test_alias_lookup_is_case_insensitive(temp_db):
    conn = _conn(temp_db)
    seed_id = _seed_one(conn, "Python", aliases=["python3"])
    result = canonicalize("Python3", conn)
    assert result == seed_id
    conn.close()


def test_canonical_lookup_case_insensitive(temp_db):
    """Input matches the canonical name directly, just different case."""
    conn = _conn(temp_db)
    seed_id = _seed_one(conn, "Docker")
    result = canonicalize("docker", conn)
    assert result == seed_id
    conn.close()


def test_auto_insert_unknown_skill(temp_db):
    conn = _conn(temp_db)
    skill_id = canonicalize("some-novel-skill-xyz", conn)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT canonical, source, category FROM skills_catalog WHERE id = %s", (skill_id,))
        row = cur.fetchone()
    assert row["canonical"] == "some-novel-skill-xyz"
    assert row["source"] == "auto"
    assert row["category"] == "other"
    conn.close()


def test_duplicate_calls_return_same_id(temp_db):
    conn = _conn(temp_db)
    id1 = canonicalize("another-new-skill", conn)
    id2 = canonicalize("another-new-skill", conn)
    conn.commit()
    assert id1 == id2
    conn.close()


def test_batch_canonicalize_returns_one_id_per_skill(temp_db):
    conn = _conn(temp_db)
    _seed_one(conn, "React", aliases=["reactjs"])
    _seed_one(conn, "Python", aliases=["py"])
    ids = batch_canonicalize(["reactjs", "py", "brand-new-tool"], conn)
    conn.commit()
    assert len(ids) == 3
    assert ids[0] != ids[1]  # React != Python
    conn.close()


def test_batch_canonicalize_dedupes_within_batch(temp_db):
    """Passing the same skill twice returns the same id both times."""
    conn = _conn(temp_db)
    ids = batch_canonicalize(["typescript", "typescript"], conn)
    conn.commit()
    assert ids[0] == ids[1]
    conn.close()


def test_caller_owns_commit(temp_db):
    """canonicalize writes to DB but does not commit; rollback discards it."""
    conn = _conn(temp_db)
    canonicalize("skill-that-should-vanish", conn)
    conn.rollback()  # caller rolls back

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM skills_catalog WHERE canonical = %s",
            ("skill-that-should-vanish",),
        )
        row = cur.fetchone()
    assert row is None, "Rollback should have discarded the auto-insert"
    conn.close()


def test_seeded_python_resolves_via_alias(temp_db):
    """After migration runs, 'py' should resolve to the seeded Python entry."""
    conn = _conn(temp_db)
    skill_id = canonicalize("py", conn)
    with conn.cursor() as cur:
        cur.execute("SELECT canonical FROM skills_catalog WHERE id = %s", (skill_id,))
        row = cur.fetchone()
    assert row["canonical"] == "Python"
    conn.close()


def test_seeded_kubernetes_k8s_alias(temp_db):
    conn = _conn(temp_db)
    id_k8s = canonicalize("k8s", conn)
    id_kubernetes = canonicalize("Kubernetes", conn)
    assert id_k8s == id_kubernetes
    conn.close()


def test_seeded_postgres_aliases(temp_db):
    conn = _conn(temp_db)
    ids = [canonicalize(a, conn) for a in ["postgres", "psql", "pgsql", "pg", "PostgreSQL"]]
    assert len(set(ids)) == 1, "All PostgreSQL aliases must resolve to the same skill_id"
    conn.close()


def test_seeded_aws_abbreviation(temp_db):
    conn = _conn(temp_db)
    id_abbr = canonicalize("amazon web services", conn)
    id_canon = canonicalize("AWS", conn)
    assert id_abbr == id_canon
    conn.close()


def test_seed_catalog_count(temp_db):
    """Sanity check: at least 200 curated canonical entries loaded."""
    conn = _conn(temp_db)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM skills_catalog WHERE source = 'curated'")
        count = cur.fetchone()["cnt"]
    assert count >= 200, f"Expected ≥200 seeded skills, got {count}"
    conn.close()


def test_seed_alias_count(temp_db):
    """Sanity check: at least 80 aliases loaded."""
    conn = _conn(temp_db)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM skill_aliases")
        count = cur.fetchone()["cnt"]
    assert count >= 80, f"Expected ≥80 aliases, got {count}"
    conn.close()
