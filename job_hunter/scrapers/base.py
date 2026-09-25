from abc import ABC, abstractmethod
import asyncio
import random
import logging
from typing import AsyncIterator

from job_hunter.models import ScrapedJob, JobSource
from job_hunter.config import settings

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """Abstract base class for all job scrapers."""

    source: JobSource
    name: str = "BaseScraper"

    def __init__(self):
        self.logger = logging.getLogger(f"job_hunter.scrapers.{self.name}")

    async def random_delay(self):
        delay = random.uniform(settings.request_delay_min, settings.request_delay_max)
        logger.debug(f"[{self.name}] Sleeping {delay:.1f}s")
        await asyncio.sleep(delay)

    @abstractmethod
    async def scrape(self, keywords: list[str] | None = None) -> list[ScrapedJob]:
        """Scrape jobs and return a list of ScrapedJob models."""
        ...

    async def safe_scrape(self, keywords: list[str] | None = None) -> list[ScrapedJob]:
        """Wrapper with error handling."""
        try:
            logger.info(f"[{self.name}] Starting scrape...")
            jobs = await self.scrape(keywords)
            logger.info(f"[{self.name}] Found {len(jobs)} jobs")
            return jobs
        except Exception as e:
            logger.error(f"[{self.name}] Scrape failed: {e}", exc_info=True)
            return []
