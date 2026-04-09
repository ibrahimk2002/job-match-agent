from pipeline.extract import extract_job_data
from pipeline.match1 import run_stage1_matching
from pipeline.match2 import run_stage2_matching
from db import get_top_matches, init_db
from utils.utils import setup_logging

def run_pipeline(profile):
    init_db()
    setup_logging()
    extract_job_data()
    run_stage1_matching(profile)
    run_stage2_matching(profile)
    return get_top_matches()
