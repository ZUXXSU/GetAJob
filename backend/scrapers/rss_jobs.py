"""
RSS feed scraper — aggregates jobs from RSS feeds.
Many job boards offer RSS (We Work Remotely, AngelList, Stack Overflow Jobs, etc).
"""
import logging
import re
from datetime import datetime
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper

logger = logging.getLogger(__name__)

# Default RSS feeds — all free, no auth needed
_DEFAULT_FEEDS = [
    {
        "name": "weworkremotely_dev",
        "url": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    },
    {
        "name": "weworkremotely_fulltime",
        "url": "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
    },
]


class RSSScraper(BaseScraper):
    name = "rss"

    def fetch_jobs(self, query: str, location: str = "") -> list:
        query_lower = query.lower()
        all_jobs = []
        for feed in _DEFAULT_FEEDS:
            try:
                jobs = self._fetch_feed(feed["url"], query_lower)
                all_jobs.extend(jobs)
            except Exception as e:
                logger.warning(f"RSS feed {feed['name']} failed: {e}")
        return all_jobs

    def _fetch_feed(self, url: str, query: str) -> list:
        r = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; GetAJobBot/1.0)",
        })
        r.raise_for_status()
        root = ET.fromstring(r.text)
        # RSS: rss > channel > item
        items = root.findall(".//item")
        jobs = []
        for item in items:
            title = (item.find("title").text or "") if item.find("title") is not None else ""
            link = (item.find("link").text or "") if item.find("link") is not None else ""
            desc_raw = (item.find("description").text or "") if item.find("description") is not None else ""
            desc = BeautifulSoup(desc_raw, "lxml").get_text(separator=" ") if desc_raw else ""

            # Only keep relevant jobs by keyword match
            combined = (title + " " + desc).lower()
            if query and query not in combined:
                continue

            guid = (item.find("guid").text or link) if item.find("guid") is not None else link

            # WeWorkRemotely titles look like "Company: Job Title"
            company = ""
            t = title
            if ":" in title:
                company, _, t = title.partition(":")
                company = company.strip()
                t = t.strip()

            jobs.append({
                "source": "rss",
                "external_id": re.sub(r'\W+', '', guid)[:100] or link[:100],
                "title": t or title,
                "company": company or "Unknown",
                "location": "Remote",
                "salary_min": None,
                "salary_max": None,
                "salary_text": "",
                "description": desc[:2000],
                "url": link,
                "posted_date": None,
            })
        return jobs[:20]  # cap per feed
