# src/skills.py
from utils import log_info


def canonicalize(skill_text: str, conn) -> int:
    normalized = skill_text.strip().lower()

    with conn.cursor() as cur:
        cur.execute("SELECT skill_id FROM skill_aliases WHERE alias = %s", (normalized,))
        row = cur.fetchone()
        if row:
            return row["skill_id"]

        cur.execute(
            "SELECT id FROM skills_catalog WHERE LOWER(canonical) = %s", (normalized,)
        )
        row = cur.fetchone()
        if row:
            return row["id"]

        cur.execute(
            "INSERT INTO skills_catalog (canonical, category, source) VALUES (%s, 'other', 'auto') RETURNING id",
            (skill_text.strip(),),
        )
        return cur.fetchone()["id"]


def batch_canonicalize(skills: list[str], conn) -> list[int]:
    total = len(skills)
    ids: list[int] = []
    cache: dict[str, int] = {}

    print(f"  Canonicalizing {total} skills...", flush=True)
    for skill in skills:
        key = skill.strip().lower()
        if key in cache:
            ids.append(cache[key])
            continue
        skill_id = canonicalize(skill, conn)
        cache[key] = skill_id
        ids.append(skill_id)

    log_info(f"skills: batch_canonicalize total={total} unique={len(cache)}")
    print(f"  Done: {len(cache)} unique skills resolved.", flush=True)
    return ids
