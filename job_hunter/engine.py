import asyncio
import logging
from datetime import datetime

from job_hunter.config import settings
from job_hunter.db.database import Database
from job_hunter.ai.scorer import JobScorer
from job_hunter.bot.telegram_bot import JobHunterBot
from job_hunter.scrapers import get_all_scrapers
from job_hunter.profile import load_profile
from job_hunter.models import JobStatus

logger = logging.getLogger(__name__)

class JobHunterEngine:
    def __init__(self):
        self.db = Database(settings.db_path)
        self.profile = load_profile()
        self.scorer = JobScorer(profile=self.profile)
        self.bot = JobHunterBot(db=self.db, scorer=self.scorer, profile=self.profile)
        self.scrapers = get_all_scrapers()

    async def start(self):
        await self.db.connect()
        logger.info("Job Hunter Engine started")
        # Run initial scrape
        await self.run_scrape_cycle()
        # Start the Telegram bot (this blocks)
        await self.bot.start()

    async def run_scrape_cycle(self):
        """Run one full cycle: scrape -> score -> notify."""
        # 1. Scrape all sources
        all_jobs = []
        tasks = [scraper.safe_scrape(settings.search_keywords) for scraper in self.scrapers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, list):
                all_jobs.extend(result)

        # 2. Save new jobs to DB
        new_count = 0
        for job in all_jobs:
            saved = await self.db.insert_job(job)
            if saved:
                new_count += 1
        logger.info(f"Saved {new_count} new jobs out of {len(all_jobs)} scraped")

        # 3. Score unscored jobs
        unscored = await self.db.get_unscored_jobs()
        for job in unscored:
            score = await self.scorer.score_job(job)
            if score and job.id:
                await self.db.update_job_score(job.id, score)

        # 4. Notify about top matches
        top_jobs = await self.db.get_top_matches(min_score=settings.min_match_score)
        for job in top_jobs:
            if job.status == JobStatus.SCORED:
                await self.bot.notify_job(job)
                if job.id:
                    await self.db.update_job_status(job.id, JobStatus.NOTIFIED)

        logger.info(f"Scrape cycle complete. Stats: {await self.db.get_stats()}")

    async def shutdown(self):
        await self.db.close()
        logger.info("Job Hunter Engine stopped")
