from pydantic import BaseModel, Field, HttpUrl
from enum import Enum
from datetime import datetime
from typing import Optional

class JobSource(str, Enum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    REMOTEOK = "remoteok"
    WELLFOUND = "wellfound"
    WEWORKREMOTELY = "weworkremotely"

class JobStatus(str, Enum):
    NEW = "new"
    SCORED = "scored"
    NOTIFIED = "notified"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"
    SKIPPED = "skipped"

class ScrapedJob(BaseModel):
    """Raw job data from a scraper."""
    title: str
    company: str
    location: str = "Remote"
    description: str
    url: str  # Use str, not HttpUrl to avoid serialization issues
    source: JobSource
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "USD"
    posted_date: Optional[datetime] = None
    tags: list[str] = Field(default_factory=list)
    remote: bool = False
    experience_level: Optional[str] = None
    apply_url: Optional[str] = None

class MatchScore(BaseModel):
    """AI-generated match assessment."""
    overall_score: int = Field(ge=0, le=100)
    skill_match: int = Field(ge=0, le=100)
    experience_match: int = Field(ge=0, le=100)
    culture_fit: int = Field(ge=0, le=100)
    matching_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    summary: str = ""
    custom_cover_letter_points: list[str] = Field(default_factory=list)

class Job(BaseModel):
    """Full job record with scoring and status tracking."""
    id: Optional[int] = None
    title: str
    company: str
    location: str = "Remote"
    description: str
    url: str
    source: JobSource
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "USD"
    posted_date: Optional[datetime] = None
    tags: list[str] = Field(default_factory=list)
    remote: bool = False
    experience_level: Optional[str] = None
    apply_url: Optional[str] = None
    status: JobStatus = JobStatus.NEW
    match_score: Optional[MatchScore] = None
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    applied_at: Optional[datetime] = None
    fingerprint: str = ""  # For deduplication

class UserProfile(BaseModel):
    """User's resume and preferences for AI matching."""
    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin_url: str = ""
    portfolio_url: str = ""
    resume_path: str = ""
    target_titles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    experience_years: int = 0
    education: str = ""
    preferred_locations: list[str] = Field(default_factory=list)
    remote_only: bool = True
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    salary_currency: str = "USD"
    bio: str = ""
    work_history: list[dict] = Field(default_factory=list)
