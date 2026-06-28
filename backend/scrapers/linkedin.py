import random
import time

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper

_UA = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


class LinkedInScraper(BaseScraper):
    name = "linkedin"
    _BASE = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    def fetch_jobs(self, query: str, location: str = "Mumbai, Maharashtra, India") -> list:
        time.sleep(random.uniform(2, 5))
        headers = {
            "User-Agent": random.choice(_UA),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.linkedin.com/jobs/search/",
        }
        params = {
            "keywords": query,
            "location": location or "Mumbai, Maharashtra, India",
            "start": "0",
            "count": "25",
        }
        r = requests.get(self._BASE, headers=headers, params=params, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        jobs = []
        for card in soup.find_all("div", class_="base-card"):
            title_tag = card.find("h3", class_="base-search-card__title")
            company_tag = card.find("h4", class_="base-search-card__subtitle")
            loc_tag = card.find("span", class_="job-search-card__location")
            link_tag = card.find("a", class_="base-card__full-link")
            if not title_tag:
                continue
            link = link_tag["href"].split("?")[0] if link_tag else ""
            ext_id = link.rstrip("/").split("-")[-1] if link else ""
            jobs.append({
                "source": "linkedin",
                "external_id": ext_id,
                "title": title_tag.get_text(strip=True),
                "company": company_tag.get_text(strip=True) if company_tag else "",
                "location": loc_tag.get_text(strip=True) if loc_tag else location,
                "salary_min": None,
                "salary_max": None,
                "salary_text": "",
                "description": "",
                "url": link,
                "posted_date": None,
            })
        return jobs
