import httpx
from bs4 import BeautifulSoup
from typing import Optional

from job_hunter.models import ScrapedJob, JobSource
from job_hunter.scrapers.base import BaseScraper
from job_hunter.config import settings


class AshbyScraper(BaseScraper):
    source = JobSource.ASHBY
    name = "AshbyScraper"

    async def scrape(self, keywords: list[str] | None = None) -> list[ScrapedJob]:
        jobs: list[ScrapedJob] = []
        
        if not hasattr(settings, 'ashby_companies') or not settings.ashby_companies:
            return jobs

        query = """
        query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {
          jobBoard: jobBoardWithTeams(organizationHostedJobsPageName: $organizationHostedJobsPageName) {
            teams {
              name
              jobs {
                title
                id
                locationName
                employmentType
                secondaryLocations {
                  locationName
                }
              }
            }
          }
        }
        """

        async with httpx.AsyncClient(timeout=30.0) as client:
            for company in settings.ashby_companies:
                url = "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams"
                payload = {
                    "operationName": "ApiJobBoardWithTeams",
                    "variables": {"organizationHostedJobsPageName": company},
                    "query": query
                }
                
                try:
                    await self.random_delay()
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    
                    job_board = data.get("data", {}).get("jobBoard", {})
                    teams = job_board.get("teams", []) if job_board else []
                    
                    for team in teams:
                        team_name = team.get("name", "")
                        team_jobs = team.get("jobs", [])
                        
                        for job_data in team_jobs:
                            title = job_data.get("title", "")
                            job_id = job_data.get("id")
                            location = job_data.get("locationName", "")
                            
                            if keywords:
                                match = any(keyword.lower() in title.lower() for keyword in keywords)
                                if not match:
                                    continue
                            
                            # Fetch job detail for description
                            job_url = f"https://jobs.ashbyhq.com/{company}/{job_id}"
                            await self.random_delay()
                            detail_response = await client.get(job_url)
                            description = ""
                            if detail_response.status_code == 200:
                                soup = BeautifulSoup(detail_response.text, "html.parser")
                                # Ashby usually puts job description in a specific div but fallback to text
                                desc_div = soup.find("div", class_="ashby-job-description")
                                if desc_div:
                                    description = desc_div.get_text(separator="\n", strip=True)
                                else:
                                    description = soup.get_text(separator="\n", strip=True)
                            
                            is_remote = "remote" in location.lower() or "remote" in title.lower()
                            
                            job = ScrapedJob(
                                title=title,
                                company=company.title(),
                                location=location if location else "Remote",
                                description=description,
                                url=job_url,
                                source=self.source,
                                remote=is_remote,
                                apply_url=job_url,
                                tags=[team_name] if team_name else []
                            )
                            jobs.append(job)
                except Exception as e:
                    self.logger.error(f"[{self.name}] Error scraping company {company}: {e}")

        return jobs
