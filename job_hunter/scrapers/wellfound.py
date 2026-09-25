import asyncio
from typing import Optional
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from job_hunter.models import ScrapedJob, JobSource
from job_hunter.scrapers.base import BaseScraper


class WellfoundScraper(BaseScraper):
    source = JobSource.WELLFOUND
    name = "WellfoundScraper"

    async def scrape(self, keywords: list[str] | None = None) -> list[ScrapedJob]:
        jobs: list[ScrapedJob] = []
        
        keywords_to_search = keywords if keywords else ["software-engineer"]
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
                locale="en-US"
            )
            page = await context.new_page()

            for keyword in keywords_to_search:
                # slugify keyword
                slug = keyword.lower().replace(" ", "-")
                url = f"https://wellfound.com/role/{slug}"
                
                try:
                    await self.random_delay()
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    
                    # Scroll down to load jobs
                    for _ in range(5):
                        await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                        await asyncio.sleep(2)
                        
                    # Find job cards
                    job_cards = await page.locator('div[class*="styles_jobCard"]').all()
                    
                    for card in job_cards:
                        try:
                            title_el = card.locator('h2, [class*="styles_title"]')
                            title = await title_el.first.inner_text() if await title_el.count() > 0 else ""
                            
                            company_el = card.locator('h2, [class*="styles_name"]')
                            company = await company_el.first.inner_text() if await company_el.count() > 0 else ""
                            
                            location_el = card.locator('[class*="styles_location"]')
                            location = await location_el.first.inner_text() if await location_el.count() > 0 else "Remote"
                            
                            link_el = card.locator('a')
                            relative_url = await link_el.first.get_attribute("href") if await link_el.count() > 0 else ""
                            
                            if not title or not company or not relative_url:
                                continue
                                
                            job_url = f"https://wellfound.com{relative_url}" if relative_url.startswith("/") else relative_url
                            
                            job = ScrapedJob(
                                title=title.strip(),
                                company=company.strip(),
                                location=location.strip(),
                                description="Description requires fetching detail page.", # Can be expanded to fetch detail
                                url=job_url,
                                source=self.source,
                                remote="remote" in location.lower() or "remote" in title.lower()
                            )
                            jobs.append(job)
                        except Exception as e:
                            self.logger.error(f"[{self.name}] Error parsing job card: {e}")
                            
                except PlaywrightTimeoutError:
                    self.logger.error(f"[{self.name}] Timeout loading Wellfound URL: {url}")
                except Exception as e:
                    self.logger.error(f"[{self.name}] Error scraping Wellfound: {e}")

            await browser.close()

        return jobs
