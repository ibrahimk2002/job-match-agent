import argparse
import os
import sys

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

    args = parser.parse_args(argv)

    if args.command == "migrate":
        _cmd_migrate(args)
    elif args.command == "run":
        _cmd_run(args)
    elif args.command == "ingest-resume":
        _cmd_ingest_resume(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
