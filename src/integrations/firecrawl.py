from utils.config import config
from firecrawl import Firecrawl

def search_jobs(query):
    app = Firecrawl(api_key=config.FIRECRAWL_API_KEY)
    try:
        results = app.search(query=query, limit=10)
        return [{"url": r.url, "title": r.title or 'Unknown', "description": r.description or ''} for r in (results.web or [])]
    except Exception as e:
        print(f"Firecrawl search error: {e}")
        return []

def scrape_job(url):    
    app = Firecrawl(api_key=config.FIRECRAWL_API_KEY)
    try:
        doc = app.scrape(url=url, formats=["markdown"], only_main_content=True)
        return doc.markdown or ''
    except Exception as e:
        print(f"Firecrawl scrape error: {e}")
        return ""
