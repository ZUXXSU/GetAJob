import logging

import requests

from .base import BaseScraper
from config import RAPIDAPI_KEY

logger = logging.getLogger(__name__)

_SUBSCRIBED = True  # set to False if /search returns 404 (wrong RapidAPI plan)


class JSearchScraper(BaseScraper):
    name = "jsearch"

    def fetch_jobs(self, query: str, location: str = "mumbai, india") -> list:
        global _SUBSCRIBED
        if not RAPIDAPI_KEY or not _SUBSCRIBED:
            return []
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": "jsearch.p.rapidapi.com",
        }
        params = {
            "query": f"{query} in {location or 'mumbai india'}",
            "page": "1",
            "num_pages": "2",
            "date_posted": "week",
        }
        r = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            headers=headers, params=params, timeout=20,
        )
        if r.status_code == 404:
            _SUBSCRIBED = False
            logger.warning(
                "JSearch /search not available on current RapidAPI plan. "
                "Go to rapidapi.com → search 'JSearch' → subscribe to 'BASIC' (free 200 req/month). "
                "Disabling JSearch for this session."
            )
            return []
        r.raise_for_status()
        data = r.json()
        jobs = []
        for item in data.get("data", []):
            sal_min = item.get("job_min_salary")
            sal_max = item.get("job_max_salary")
            currency = item.get("job_salary_currency", "")
            if currency == "USD" and sal_min:
                sal_min = round(sal_min * 83)
                sal_max = round((sal_max or sal_min) * 83)
            city = item.get("job_city", "")
            country = item.get("job_country", "")
            loc = ", ".join(filter(None, [city, country]))
            jobs.append({
                "source": "jsearch",
                "external_id": item.get("job_id", ""),
                "title": item.get("job_title", ""),
                "company": item.get("employer_name", ""),
                "location": loc,
                "salary_min": sal_min,
                "salary_max": sal_max,
                "salary_text": item.get("job_salary_period", ""),
                "description": item.get("job_description", ""),
                "url": item.get("job_apply_link", ""),
                "posted_date": item.get("job_posted_at_datetime_utc"),
            })
        return jobs
