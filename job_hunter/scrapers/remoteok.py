import httpx
from datetime import datetime
from bs4 import BeautifulSoup
from typing import Optional

from job_hunter.models import ScrapedJob, JobSource
from job_hunter.scrapers.base import BaseScraper


class RemoteOKScraper(BaseScraper):
    source = JobSource.REMOTEOK
    name = "RemoteOKScraper"

    async def scrape(self, keywords: list[str] | None = None) -> list[ScrapedJob]:
        jobs: list[ScrapedJob] = []
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }

        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            url = "https://remoteok.com/api"
            try:
                await self.random_delay()
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                
                # First element is metadata
                if data and isinstance(data, list):
                    job_listings = data[1:]
                else:
                    job_listings = []
                
                for job_data in job_listings:
                    title = job_data.get("position", "")
                    company = job_data.get("company", "")
                    location = job_data.get("location", "Remote")
                    description_html = job_data.get("description", "")
                    relative_url = job_data.get("url", "")
                    job_url = f"https://remoteok.com{relative_url}" if relative_url.startswith("/") else relative_url
                    tags = job_data.get("tags", [])
                    salary_min = job_data.get("salary_min")
                    salary_max = job_data.get("salary_max")
                    
                    if keywords:
                        match = any(keyword.lower() in title.lower() or keyword.lower() in " ".join(tags).lower() for keyword in keywords)
                        if not match:
                            continue
                    
                    soup = BeautifulSoup(description_html, "html.parser")
                    description = soup.get_text(separator="\n", strip=True)
                    
                    posted_date = None
                    date_str = job_data.get("date")
                    if date_str:
                        try:
                            # Parse ISO format datetime
                            posted_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        except ValueError:
                            pass

                    job = ScrapedJob(
                        title=title,
                        company=company,
                        location=location,
                        description=description,
                        url=job_url,
                        source=self.source,
                        salary_min=salary_min if isinstance(salary_min, int) and salary_min > 0 else None,
                        salary_max=salary_max if isinstance(salary_max, int) and salary_max > 0 else None,
                        remote=True,
                        posted_date=posted_date,
                        tags=tags
                    )
                    jobs.append(job)
            except Exception as e:
                self.logger.error(f"[{self.name}] Error scraping RemoteOK: {e}")

        return jobs
