import asyncio
import urllib.parse
from typing import Optional
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from job_hunter.models import ScrapedJob, JobSource
from job_hunter.scrapers.base import BaseScraper


class IndeedScraper(BaseScraper):
    source = JobSource.INDEED
    name = "IndeedScraper"

    async def scrape(self, keywords: list[str] | None = None) -> list[ScrapedJob]:
        jobs: list[ScrapedJob] = []
        
        keywords_to_search = keywords if keywords else ["software engineer"]
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768},
                locale="en-US",
                timezone_id="America/New_York"
            )
            page = await context.new_page()

            for keyword in keywords_to_search:
                encoded_keyword = urllib.parse.quote_plus(keyword)
                # DSQF7 is Remote filter
                url = f"https://www.indeed.com/jobs?q={encoded_keyword}&sc=0kf%3Aattr(DSQF7)%3B"
                
                try:
                    # Longer delay for Indeed to avoid anti-bot
                    await asyncio.sleep(3)
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    
                    # Anti-bot check
                    title_text = await page.title()
                    if "Cloudflare" in title_text or "human" in title_text.lower() or "robot" in title_text.lower():
                        self.logger.warning(f"[{self.name}] Hit Indeed anti-bot challenge.")
                        continue
                        
                    # Simulate human scrolling
                    for _ in range(3):
                        await page.evaluate("window.scrollBy(0, window.innerHeight)")
                        await asyncio.sleep(1.5)
                        
                    job_cards = await page.locator('div.job_seen_beacon, td.resultContent').all()
                    
                    for card in job_cards:
                        try:
                            title_el = card.locator('h2.jobTitle a')
                            title = await title_el.inner_text() if await title_el.count() > 0 else ""
                            
                            company_el = card.locator('span[data-testid="company-name"]')
                            company = await company_el.inner_text() if await company_el.count() > 0 else ""
                            
                            location_el = card.locator('div[data-testid="text-location"]')
                            location = await location_el.inner_text() if await location_el.count() > 0 else "Remote"
                            
                            job_key = await title_el.get_attribute("data-jk") if await title_el.count() > 0 else ""
                            
                            if not title or not company or not job_key:
                                continue
                                
                            job_url = f"https://www.indeed.com/viewjob?jk={job_key}"
                            
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
                            self.logger.error(f"[{self.name}] Error parsing job card: {e}")
                            
                except PlaywrightTimeoutError:
                    self.logger.error(f"[{self.name}] Timeout loading Indeed URL: {url}")
                except Exception as e:
                    self.logger.error(f"[{self.name}] Error scraping Indeed: {e}")

            await browser.close()

        return jobs
