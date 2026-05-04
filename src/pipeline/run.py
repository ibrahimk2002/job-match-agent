from .extract import extract_job_data
from .match1 import run_stage1_matching
from .match2 import run_stage2_matching
from .ingest import ingest_data
from db import get_top_matches, init_db
from utils import setup_logging

def run_pipeline():
    init_db()
    print("Database initialized.")
    setup_logging()
    print("Logging configured.")
    ingest_data()
    print("Data ingestion completed.")
    print("Starting data extraction...")
    extract_job_data()
    print("Data extraction completed.")
    # run_stage1_matching(profile)
    # run_stage2_matching(profile)
    # return get_top_matches()
    return []
