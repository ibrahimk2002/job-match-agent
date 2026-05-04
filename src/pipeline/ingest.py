import os

from db import import_jobs_from_jsonl
from utils import log_info


def discover_report_jsonl_files(reports_dir: str) -> list[str]:
    """Find cleaned_jobs.jsonl files in every batch subdirectory under data/reports."""
    jsonl_files: list[str] = []
    if not os.path.isdir(reports_dir):
        return jsonl_files

    for entry in os.scandir(reports_dir):
        if not entry.is_dir():
            continue
        candidate = os.path.join(entry.path, "cleaned_jobs.jsonl")
        if os.path.isfile(candidate):
            jsonl_files.append(candidate)

    jsonl_files.sort()
    return jsonl_files


def ingest_data() -> int:
    """Discover report batches dynamically and ingest all cleaned JSONL files."""
    reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'reports'))
    total_inserted = 0
    jsonl_files = discover_report_jsonl_files(reports_dir)

    for path in jsonl_files:
        inserted = import_jobs_from_jsonl(path)
        total_inserted += inserted
        log_info(f"Ingested {inserted} new jobs from {os.path.basename(path)}")

    log_info(f"Ingestion complete. Discovered {len(jsonl_files)} report batch files; inserted {total_inserted} new jobs")
    return total_inserted
