import asyncio
import urllib.parse
from typing import Optional
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from job_hunter.models import ScrapedJob, JobSource
from job_hunter.scrapers.base import BaseScraper


class LinkedInScraper(BaseScraper):
    source = JobSource.LINKEDIN
    name = "LinkedInScraper"

    async def scrape(self, keywords: list[str] | None = None) -> list[ScrapedJob]:
        jobs: list[ScrapedJob] = []
        
        keywords_to_search = keywords if keywords else ["software engineer"]
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768},
                locale="en-US"
            )
            page = await context.new_page()

            for keyword in keywords_to_search:
                encoded_keyword = urllib.parse.quote_plus(keyword)
                # f_WT=2 is for Remote jobs
                url = f"https://www.linkedin.com/jobs/search/?keywords={encoded_keyword}&location=Worldwide&f_WT=2"
                
                try:
                    await self.random_delay()
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    
                    # Scroll to load more
                    for _ in range(5):
                        await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                        await asyncio.sleep(2)
                        
                    job_elements = await page.locator("ul.jobs-search__results-list > li").all()
                    
                    for li in job_elements:
                        try:
                            title_el = li.locator("h3.base-search-card__title")
                            title = await title_el.inner_text() if await title_el.count() > 0 else ""
                            
                            company_el = li.locator("h4.base-search-card__subtitle")
                            company = await company_el.inner_text() if await company_el.count() > 0 else ""
                            
                            location_el = li.locator("span.job-search-card__location")
                            location = await location_el.inner_text() if await location_el.count() > 0 else "Remote"
                            
                            link_el = li.locator("a.base-card__full-link")
                            job_url = await link_el.get_attribute("href") if await link_el.count() > 0 else ""
                            
                            if not title or not company or not job_url:
                                continue
                                
                            # Clean tracking from URL
                            job_url = job_url.split("?")[0]
                            
                            job = ScrapedJob(
                                title=title.strip(),
                                company=company.strip(),
                                location=location.strip(),
                                description="Description requires fetching detail page.", # Expandable
                                url=job_url,
                                source=self.source,
                                remote=True
                            )
                            jobs.append(job)
                        except Exception as e:
                            self.logger.error(f"[{self.name}] Error parsing job listing: {e}")
                            
                except PlaywrightTimeoutError:
                    self.logger.error(f"[{self.name}] Timeout loading LinkedIn URL: {url}")
                except Exception as e:
                    self.logger.error(f"[{self.name}] Error scraping LinkedIn: {e}")

            await browser.close()

        return jobs
