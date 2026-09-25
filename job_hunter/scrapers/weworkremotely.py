import httpx
from bs4 import BeautifulSoup
import urllib.parse
from typing import Optional

from job_hunter.models import ScrapedJob, JobSource
from job_hunter.scrapers.base import BaseScraper


class WeWorkRemotelyScraper(BaseScraper):
    source = JobSource.WEWORKREMOTELY
    name = "WeWorkRemotelyScraper"

    async def scrape(self, keywords: list[str] | None = None) -> list[ScrapedJob]:
        jobs: list[ScrapedJob] = []
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }
        
        keywords_to_search = keywords if keywords else [""]

        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            for keyword in keywords_to_search:
                encoded_keyword = urllib.parse.quote_plus(keyword)
                url = f"https://weworkremotely.com/remote-jobs/search?term={encoded_keyword}"
                try:
                    await self.random_delay()
                    response = await client.get(url)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.text, "html.parser")
                    job_sections = soup.find_all("section", class_="jobs")
                    
                    for section in job_sections:
                        listings = section.find_all("li", class_=lambda x: x and "feature" in x or "job" in x)
                        for li in listings:
                            a_tag = li.find("a", recursive=False)
                            if not a_tag or "href" not in a_tag.attrs:
                                # Sometimes structure is different
                                a_tags = li.find_all("a")
                                if not a_tags:
                                    continue
                                # Find the first valid job link
                                a_tag = next((a for a in a_tags if a.get("href", "").startswith("/remote-jobs/")), None)
                                if not a_tag:
                                    continue
                                
                            relative_url = a_tag["href"]
                            job_url = f"https://weworkremotely.com{relative_url}"
                            
                            company_elem = a_tag.find("span", class_="company")
                            title_elem = a_tag.find("span", class_="title")
                            location_elem = a_tag.find("span", class_="region")
                            
                            if not company_elem or not title_elem:
                                continue
                                
                            company = company_elem.text.strip()
                            title = title_elem.text.strip()
                            location = location_elem.text.strip() if location_elem else "Remote"
                            
                            # Fetch job detail for description
                            await self.random_delay()
                            detail_response = await client.get(job_url)
                            description = ""
                            if detail_response.status_code == 200:
                                detail_soup = BeautifulSoup(detail_response.text, "html.parser")
                                desc_div = detail_soup.find("div", class_="listing-container")
                                if desc_div:
                                    description = desc_div.get_text(separator="\n", strip=True)
                                else:
                                    description = detail_soup.get_text(separator="\n", strip=True)
                                    
                            job = ScrapedJob(
                                title=title,
                                company=company,
                                location=location,
                                description=description,
                                url=job_url,
                                source=self.source,
                                remote=True
                            )
                            jobs.append(job)
                except Exception as e:
                    self.logger.error(f"[{self.name}] Error scraping keyword '{keyword}': {e}")

        return jobs
