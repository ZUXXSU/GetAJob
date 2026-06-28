import random
import time

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper

_TAG_MAP = {
    "flutter developer": "flutter",
    "ios developer swift": "ios",
    "android developer kotlin": "android",
    "mobile developer": "mobile",
    "react native developer": "react-native",
    "full stack developer": "fullstack",
    "software developer": "javascript",
}

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


class RemoteOKScraper(BaseScraper):
    name = "remoteok"
    _BASE = "https://remoteok.com/api"

    def fetch_jobs(self, query: str, location: str = "") -> list:
        tag = _TAG_MAP.get(query.lower(), query.split()[0].lower())
        time.sleep(random.uniform(1, 2))
        r = requests.get(
            self._BASE,
            params={"tag": tag},
            headers={"User-Agent": _UA},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        jobs = []
        for item in data:
            if not isinstance(item, dict) or not item.get("position"):
                continue
            desc_html = item.get("description", "")
            desc = BeautifulSoup(desc_html, "lxml").get_text(separator=" ") if desc_html else ""
            tags = " ".join(item.get("tags", []))
            jobs.append({
                "source": "remoteok",
                "external_id": str(item.get("id", "")),
                "title": item.get("position", ""),
                "company": item.get("company", ""),
                "location": f"Remote — {item.get('location', 'Worldwide')}",
                "salary_min": item.get("salary_min") or None,
                "salary_max": item.get("salary_max") or None,
                "salary_text": f"${item['salary_min']}-${item['salary_max']}/yr" if item.get("salary_min") else "",
                "description": f"{desc} Skills: {tags}",
                "url": item.get("url", f"https://remoteok.com/remote-jobs/{item.get('id','')}"),
                "posted_date": item.get("date"),
            })
        return jobs
