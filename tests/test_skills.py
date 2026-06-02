import psycopg2
import psycopg2.extras
import pytest

from skills import canonicalize, batch_canonicalize


def _conn(db_url):
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)


def _seed_one(conn, canonical, category="hard", aliases=None):
    """Insert one skill + optional aliases. Commits."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO skills_catalog (canonical, category, source) VALUES (%s, %s, 'curated') RETURNING id",
            (canonical, category),
        )
        skill_id = cur.fetchone()["id"]
        for alias in (aliases or []):
            cur.execute(
                "INSERT INTO skill_aliases (alias, skill_id) VALUES (%s, %s)",
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
