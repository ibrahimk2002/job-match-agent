import hashlib
import logging
import os

def hash_url(url):
    return hashlib.sha256(url.encode()).hexdigest()

def setup_logging():
    log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'logs'))
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        filename=os.path.join(log_dir, 'job_matcher.log'),
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def log_info(message):
    logging.info(message)

def log_error(message):
    logging.error(message)
