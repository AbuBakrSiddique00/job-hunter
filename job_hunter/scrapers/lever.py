import httpx
from typing import Optional

from job_hunter.models import ScrapedJob, JobSource
from job_hunter.scrapers.base import BaseScraper
from job_hunter.config import settings


class LeverScraper(BaseScraper):
    source = JobSource.LEVER
    name = "LeverScraper"

    async def scrape(self, keywords: list[str] | None = None) -> list[ScrapedJob]:
        jobs: list[ScrapedJob] = []
        
        if not hasattr(settings, 'lever_companies') or not settings.lever_companies:
            return jobs

        async with httpx.AsyncClient(timeout=30.0) as client:
            for company in settings.lever_companies:
                url = f"https://api.lever.co/v0/postings/{company}?mode=json"
                try:
                    await self.random_delay()
                    response = await client.get(url)
                    response.raise_for_status()
                    data = response.json()
                    
                    for job_data in data:
                        title = job_data.get("text", "")
                        categories = job_data.get("categories", {})
                        location = categories.get("location", "")
                        team = categories.get("team", "")
                        description = job_data.get("descriptionPlain", "")
                        job_url = job_data.get("hostedUrl", "")
                        apply_url = job_data.get("applyUrl", "")
                        
                        if keywords:
                            match = any(keyword.lower() in title.lower() or keyword.lower() in description.lower() for keyword in keywords)
                            if not match:
                                continue
                                
                        is_remote = "remote" in location.lower() or "remote" in title.lower()
                        
                        tags = []
                        if team:
                            tags.append(team)

                        job = ScrapedJob(
                            title=title,
                            company=company.title(),
                            location=location if location else "Remote",
                            description=description,
                            url=job_url,
                            source=self.source,
                            remote=is_remote,
                            apply_url=apply_url,
                            tags=tags
                        )
                        jobs.append(job)
                except Exception as e:
                    self.logger.error(f"[{self.name}] Error scraping company {company}: {e}")

        return jobs
