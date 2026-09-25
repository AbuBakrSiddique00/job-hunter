from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Scraping
    scrape_interval_minutes: int = 60
    min_match_score: int = 70  # Minimum score to notify
    max_concurrent_scrapers: int = 3
    request_delay_min: float = 1.0
    request_delay_max: float = 3.0

    # Database
    db_path: str = "jobs.db"

    # Target companies (for ATS scraping)
    greenhouse_companies: list[str] = Field(default_factory=lambda: ["figma", "notion", "stripe", "ramp", "linear"])
    lever_companies: list[str] = Field(default_factory=lambda: ["netlify", "postman"])
    ashby_companies: list[str] = Field(default_factory=lambda: ["linear", "notion"])

    # Search keywords
    search_keywords: list[str] = Field(default_factory=lambda: ["software engineer", "backend engineer", "full stack developer", "python developer"])

settings = Settings()
