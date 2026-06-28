import logging
import time
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    name: str = "base"

    @abstractmethod
    def fetch_jobs(self, query: str, location: str = "") -> list:
        pass

    def safe_fetch(self, query: str, location: str = "") -> list:
        for attempt in range(3):
            try:
                return self.fetch_jobs(query, location)
            except Exception as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"[{self.name}] '{query}' failed after 3 attempts: {e}")
        return []
