import requests
from .base import BaseScraper
from config import ADZUNA_APP_ID, ADZUNA_APP_KEY

BASE_URL = "https://api.adzuna.com/v1/api/jobs/in/search/1"


class AdzunaScraper(BaseScraper):
    name = "adzuna"

    def fetch_jobs(self, query: str, location: str = "mumbai") -> list:
        if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
            return []
        params = {
            "app_id": ADZUNA_APP_ID,
            "app_key": ADZUNA_APP_KEY,
            "results_per_page": 50,
            "what": query,
            "where": location or "mumbai",
            "content-type": "application/json",
        }
        r = requests.get(BASE_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        jobs = []
        for item in data.get("results", []):
            sal_min = item.get("salary_min")
            sal_max = item.get("salary_max")
            jobs.append({
                "source": "adzuna",
                "external_id": str(item.get("id", "")),
                "title": item.get("title", ""),
                "company": item.get("company", {}).get("display_name", ""),
                "location": item.get("location", {}).get("display_name", ""),
                "salary_min": sal_min,
                "salary_max": sal_max,
                "salary_text": f"{sal_min}–{sal_max}" if sal_min else "",
                "description": item.get("description", ""),
                "url": item.get("redirect_url", ""),
                "posted_date": item.get("created"),
            })
        return jobs
