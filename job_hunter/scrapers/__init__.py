from job_hunter.scrapers.greenhouse import GreenhouseScraper
from job_hunter.scrapers.lever import LeverScraper
from job_hunter.scrapers.ashby import AshbyScraper
from job_hunter.scrapers.remoteok import RemoteOKScraper
from job_hunter.scrapers.weworkremotely import WeWorkRemotelyScraper
from job_hunter.scrapers.wellfound import WellfoundScraper
from job_hunter.scrapers.linkedin import LinkedInScraper
from job_hunter.scrapers.indeed import IndeedScraper
from job_hunter.scrapers.base import BaseScraper

def get_all_scrapers() -> list[BaseScraper]:
    return [
        GreenhouseScraper(),
        LeverScraper(),
        AshbyScraper(),
        RemoteOKScraper(),
        WeWorkRemotelyScraper(),
        WellfoundScraper(),
        LinkedInScraper(),
        IndeedScraper(),
    ]

__all__ = [
    "GreenhouseScraper", "LeverScraper", "AshbyScraper",
    "RemoteOKScraper", "WeWorkRemotelyScraper", "WellfoundScraper",
    "LinkedInScraper", "IndeedScraper", "BaseScraper",
    "get_all_scrapers",
]
