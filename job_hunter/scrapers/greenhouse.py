import httpx
import re
from datetime import datetime
from typing import Optional
from bs4 import BeautifulSoup

from job_hunter.models import ScrapedJob, JobSource
from job_hunter.scrapers.base import BaseScraper
from job_hunter.config import settings


class GreenhouseScraper(BaseScraper):
    source = JobSource.GREENHOUSE
    name = "GreenhouseScraper"

    def _extract_salary(self, html_content: str) -> tuple[Optional[int], Optional[int]]:
        soup = BeautifulSoup(html_content, "html.parser")
        text = soup.get_text(separator=" ").lower()
        
        salary_pattern = re.compile(r'\$([\d,]+)\s*(?:-|to)\s*\$([\d,]+)')
        match = salary_pattern.search(text)
        if match:
            min_salary = int(match.group(1).replace(',', ''))
            max_salary = int(match.group(2).replace(',', ''))
            return min_salary, max_salary
        return None, None

    async def scrape(self, keywords: list[str] | None = None) -> list[ScrapedJob]:
        jobs: list[ScrapedJob] = []
        
        if not hasattr(settings, 'greenhouse_companies') or not settings.greenhouse_companies:
            return jobs

        async with httpx.AsyncClient(timeout=30.0) as client:
            for company in settings.greenhouse_companies:
                url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
                try:
                    await self.random_delay()
                    response = await client.get(url)
                    response.raise_for_status()
                    data = response.json()
                    
                    for job_data in data.get("jobs", []):
                        job_id = job_data.get("id")
                        title = job_data.get("title", "")
                        location_data = job_data.get("location", {})
                        location = location_data.get("name", "")
                        job_url = job_data.get("absolute_url", "")
                        
                        # Apply keyword filter if specified
                        if keywords:
                            match = any(keyword.lower() in title.lower() for keyword in keywords)
                            if not match:
                                continue

                        # Fetch job details
                        detail_url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{job_id}"
                        await self.random_delay()
                        detail_response = await client.get(detail_url)
                        
                        if detail_response.status_code == 200:
                            detail_data = detail_response.json()
                            content = detail_data.get("content", "")
                            
                            min_sal, max_sal = self._extract_salary(content)
                            
                            is_remote = "remote" in location.lower() or "remote" in title.lower()
                            
                            soup = BeautifulSoup(content, "html.parser")
                            description = soup.get_text(separator="\n", strip=True)
                            
                            job = ScrapedJob(
                                title=title,
                                company=company.title(),
                                location=location if location else "Remote",
                                description=description,
                                url=job_url,
                                source=self.source,
                                salary_min=min_sal,
                                salary_max=max_sal,
                                remote=is_remote,
                                apply_url=job_url
                            )
                            jobs.append(job)
                except Exception as e:
                    self.logger.error(f"[{self.name}] Error scraping company {company}: {e}")

        return jobs
