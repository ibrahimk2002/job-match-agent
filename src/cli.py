import argparse
import os
import sys

_SRC = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SRC)
for _p in [_SRC, _ROOT]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _cmd_ingest_resume(args: argparse.Namespace) -> None:
    if not os.path.isfile(args.pdf_path):
        print(f"Error: PDF not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)
    from pipeline.extract_resume import extract_resume
    extract_resume(args.pdf_path, args.email)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description="Job Match Agent CLI",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    resume_parser = subparsers.add_parser(
        "ingest-resume",
        help="Extract structured profile from a PDF resume",
    )
    resume_parser.add_argument("pdf_path", help="Path to the PDF resume file")
    resume_parser.add_argument("--email", required=True, help="Candidate email address")

    args = parser.parse_args(argv)

    if args.command == "ingest-resume":
        _cmd_ingest_resume(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
