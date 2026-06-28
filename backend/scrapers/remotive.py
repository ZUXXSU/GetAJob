import requests
from bs4 import BeautifulSoup

from .base import BaseScraper

_KEYWORD_MAP = {
    "flutter developer": "flutter",
    "ios developer swift": "ios",
    "android developer kotlin": "android",
    "mobile developer": "mobile",
    "react native developer": "react native",
    "full stack developer": "full stack",
    "software developer": "software",
}


class RemotiveScraper(BaseScraper):
    name = "remotive"
    _BASE = "https://remotive.com/api/remote-jobs"

    def fetch_jobs(self, query: str, location: str = "") -> list:
        term = _KEYWORD_MAP.get(query.lower(), query.split()[0])
        r = requests.get(self._BASE, params={"search": term, "limit": 50}, timeout=15)
        r.raise_for_status()
        data = r.json()
        jobs = []
        for item in data.get("jobs", []):
            raw_desc = item.get("description", "")
            desc = BeautifulSoup(raw_desc, "lxml").get_text(separator=" ") if raw_desc else ""
            candidate_loc = item.get("candidate_required_location", "Worldwide")
            jobs.append({
                "source": "remotive",
                "external_id": str(item.get("id", "")),
                "title": item.get("title", ""),
                "company": item.get("company_name", ""),
                "location": f"Remote — {candidate_loc}",
                "salary_min": None,
                "salary_max": None,
                "salary_text": item.get("salary", ""),
                "description": desc,
                "url": item.get("url", ""),
                "posted_date": item.get("publication_date"),
            })
        return jobs
