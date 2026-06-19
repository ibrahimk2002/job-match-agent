import argparse
import os
import sys
from typing import get_args

from dotenv import load_dotenv

_SRC = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SRC)
for _p in [_SRC, _ROOT]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

load_dotenv(os.path.join(_ROOT, ".env"))


def _cmd_migrate(_args: argparse.Namespace) -> None:
    from db import init_db
    init_db()
    print("Schema migrations applied.")


def _cmd_run(_args: argparse.Namespace) -> None:
    from pipeline import run_pipeline
    results = run_pipeline()
    print("Top Job Matches:")
    for result in results[:10]:
        print(f"* {result['title']} | {result['company']} | {result['score']} | {result['decision']}")


def _prompt_choice(prompt: str, options: list[str]) -> str | None:
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    raw = input("Enter number or press Enter to skip: ").strip()
    if not raw:
        return None
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(options):
            return options[idx]
    except ValueError:
        pass
    print("  Invalid choice — skipping preference.")
    return None


def _print_results(results: list[dict], label: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"{'─' * 60}")
    if not results:
        print("  No matching jobs found.")
        return
    for i, r in enumerate(results, 1):
        title = r.get("normalized_title") or r.get("title_raw") or "Unknown"
        company = r.get("company_raw") or ""
        mode = r.get("work_mode") or ""
        role = r.get("role_family") or ""
        seniority = r.get("seniority") or ""
        score = r.get("match_score") or 0
        sim = r.get("cosine_similarity") or 0
        url = r.get("source_url") or ""
        print(f"\n  #{i}  {title} | {company}")
        print(f"       Role: {role} | Seniority: {seniority} | Mode: {mode}")
        print(f"       Match score: {score:.4f} | Cosine similarity: {sim:.4f}")
        if url:
            print(f"       {url}")


def _cmd_match(args: argparse.Namespace) -> None:
    from models.job_profile import ExtractionResult
    from db import get_user_by_email, get_active_user_profile, get_stage1_matches_pgvector
    from pipeline.match1 import run_stage1_naive, timed

    role_families = [v for v in get_args(ExtractionResult.model_fields["role_family"].annotation) if v != "unknown"]
    seniority_levels = [v for v in get_args(ExtractionResult.model_fields["seniority"].annotation) if v != "unknown"]

    user = get_user_by_email(args.email)
    if user is None:
        print(f"Error: no user found with email '{args.email}'", file=sys.stderr)
        sys.exit(1)

    profile = get_active_user_profile(user["id"])
    if profile is None:
        print(f"Error: no active resume for '{args.email}'. Run 'ingest-resume' first.", file=sys.stderr)
        sys.exit(1)

    user_axes = [
        profile.get("axis_backend") or 0.0,
        profile.get("axis_frontend") or 0.0,
        profile.get("axis_platform") or 0.0,
        profile.get("axis_ai_data") or 0.0,
        profile.get("axis_security_reliability") or 0.0,
        profile.get("axis_product_ownership") or 0.0,
    ]

    preferred_role = _prompt_choice("What type of role are you interested in?", role_families)
    preferred_seniority = _prompt_choice("What seniority level are you targeting?", seniority_levels)

    print(f"\nFinding top 5 matches for {args.email}...")

    if not args.benchmark:
        results, elapsed = timed(get_stage1_matches_pgvector, user_axes, preferred_role, preferred_seniority)
        _print_results(results, f"Top 5 Matches  (pgvector · {elapsed * 1000:.1f} ms)")
        return

    pgvec_results, pgvec_time = timed(get_stage1_matches_pgvector, user_axes, preferred_role, preferred_seniority)
    naive_results, naive_time = timed(run_stage1_naive, user_axes, preferred_role, preferred_seniority)

    _print_results(pgvec_results, f"pgvector  ({pgvec_time * 1000:.1f} ms)")
    _print_results(naive_results, f"Naive Python  ({naive_time * 1000:.1f} ms)")

    speedup = naive_time / pgvec_time if pgvec_time > 0 else float("inf")
    pgvec_top = pgvec_results[0].get("normalized_title", "") if pgvec_results else ""
    naive_top = naive_results[0].get("normalized_title", "") if naive_results else ""

    print(f"\n{'─' * 60}")
    print(f"  Benchmark Summary")
    print(f"{'─' * 60}")
    print(f"  pgvector:     {pgvec_time * 1000:>8.2f} ms")
    print(f"  naive Python: {naive_time * 1000:>8.2f} ms")
    print(f"  Speedup:      {speedup:>8.1f}x")
    print(f"  Top result agrees: {'Yes' if pgvec_top == naive_top else 'NO — results differ!'}")


def _cmd_ingest_resume(args: argparse.Namespace) -> None:
    if not os.path.isfile(args.pdf_path):
        print(f"Error: PDF not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)
    from pipeline.extract_resume import extract_resume
    extract_resume(args.pdf_path, args.email)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python src/cli.py",
        description="Job Match Agent CLI",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    subparsers.add_parser("migrate", help="Apply schema migrations to the database")

    subparsers.add_parser("run", help="Run the full matching pipeline")

    resume_parser = subparsers.add_parser(
        "ingest-resume",
        help="Extract structured profile from a PDF resume",
    )
    resume_parser.add_argument("pdf_path", help="Path to the PDF resume file")
    resume_parser.add_argument("--email", required=True, help="Candidate email address")

    match_parser = subparsers.add_parser(
        "match",
        help="Find top 5 matching jobs for a user (read-only, no ingestion or extraction)",
    )
    match_parser.add_argument("--email", required=True, help="Candidate email address")
    match_parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Also run naive Python cosine matching and print a timing comparison",
    )

    args = parser.parse_args(argv)

    if args.command == "migrate":
        _cmd_migrate(args)
    elif args.command == "run":
        _cmd_run(args)
    elif args.command == "ingest-resume":
        _cmd_ingest_resume(args)
    elif args.command == "match":
        _cmd_match(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
