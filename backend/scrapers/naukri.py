import random
import time

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper

_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


class NaukriScraper(BaseScraper):
    name = "naukri"
    _BASE = "https://www.naukri.com/jobapi/v3/search"

    def fetch_jobs(self, query: str, location: str = "mumbai, thane, navi mumbai") -> list:
        time.sleep(random.uniform(1.5, 3.5))
        headers = {
            "appid": "109",
            "systemid": "109",
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept": "application/json",
            "Referer": "https://www.naukri.com/",
        }
        params = {
            "noOfResults": "50",
            "urlType": "search_by_keyword",
            "searchType": "adv",
            "keyword": query,
            "location": location,
            "jobAge": "15",
            "experience": "0",
            "salary": "0",
        }
        r = requests.get(self._BASE, headers=headers, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        jobs = []
        for item in data.get("jobDetails", []):
            salary_text = ""
            location_text = ""
            for ph in item.get("placeholders", []):
                if ph.get("type") == "salary":
                    salary_text = ph.get("label", "")
                elif ph.get("type") == "location":
                    location_text = ph.get("label", "")
            raw_desc = item.get("jobDescription", "")
            desc = BeautifulSoup(raw_desc, "lxml").get_text(separator=" ") if raw_desc else ""
            jd_url = item.get("jdURL", "")
            url = ("https://www.naukri.com" + jd_url) if jd_url else ""
            jobs.append({
                "source": "naukri",
                "external_id": str(item.get("jobId", "")),
                "title": item.get("title", ""),
                "company": item.get("companyName", ""),
                "location": location_text,
                "salary_min": None,
                "salary_max": None,
                "salary_text": salary_text,
                "description": desc,
                "url": url,
                "posted_date": None,
            })
        return jobs
