import aiosqlite
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional
import logging

from job_hunter.models import Job, JobStatus, MatchScore, ScrapedJob, JobSource

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "jobs.db"):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self):
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._create_tables()
        logger.info(f"Connected to database: {self.db_path}")

    async def close(self):
        if self._db:
            await self._db.close()
            logger.info("Database connection closed")

    async def _create_tables(self):
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT DEFAULT 'Remote',
                description TEXT NOT NULL,
                url TEXT NOT NULL,
                source TEXT NOT NULL,
                salary_min INTEGER,
                salary_max INTEGER,
                salary_currency TEXT DEFAULT 'USD',
                posted_date TEXT,
                tags TEXT DEFAULT '[]',
                remote BOOLEAN DEFAULT 0,
                experience_level TEXT,
                apply_url TEXT,
                status TEXT DEFAULT 'new',
                match_score TEXT,
                discovered_at TEXT NOT NULL,
                applied_at TEXT,
                fingerprint TEXT UNIQUE NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_fingerprint ON jobs(fingerprint);
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
            CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
            CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(status, match_score);
        """)
        await self._db.commit()

    @staticmethod
    def generate_fingerprint(title: str, company: str, url: str) -> str:
        raw = f"{title.lower().strip()}|{company.lower().strip()}|{url.strip()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def job_exists(self, fingerprint: str) -> bool:
        async with self._db.execute(
            "SELECT 1 FROM jobs WHERE fingerprint = ?", (fingerprint,)
        ) as cursor:
            return await cursor.fetchone() is not None

    async def insert_job(self, job: ScrapedJob) -> Optional[Job]:
        fingerprint = self.generate_fingerprint(job.title, job.company, job.url)
        if await self.job_exists(fingerprint):
            logger.debug(f"Duplicate job skipped: {job.title} at {job.company}")
            return None

        now = datetime.utcnow().isoformat()
        await self._db.execute(
            """INSERT INTO jobs (title, company, location, description, url, source,
               salary_min, salary_max, salary_currency, posted_date, tags, remote,
               experience_level, apply_url, status, discovered_at, fingerprint)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job.title, job.company, job.location, job.description, job.url,
                job.source.value, job.salary_min, job.salary_max, job.salary_currency,
                job.posted_date.isoformat() if job.posted_date else None,
                json.dumps(job.tags), job.remote, job.experience_level,
                job.apply_url, JobStatus.NEW.value, now, fingerprint,
            ),
        )
        await self._db.commit()
        logger.info(f"New job saved: {job.title} at {job.company}")
        return Job(
            title=job.title, company=job.company, location=job.location,
            description=job.description, url=job.url, source=job.source,
            salary_min=job.salary_min, salary_max=job.salary_max,
            salary_currency=job.salary_currency, posted_date=job.posted_date,
            tags=job.tags, remote=job.remote, experience_level=job.experience_level,
            apply_url=job.apply_url, fingerprint=fingerprint, discovered_at=datetime.fromisoformat(now),
        )

    async def get_job_by_id(self, job_id: int) -> Optional[Job]:
        """Fetch a single job by its primary key."""
        async with self._db.execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_job(row)
            return None

    async def get_unscored_jobs(self, limit: int = 50) -> list[Job]:
        async with self._db.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY discovered_at DESC LIMIT ?",
            (JobStatus.NEW.value, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_job(row) for row in rows]

    async def update_job_score(self, job_id: int, score: MatchScore):
        await self._db.execute(
            "UPDATE jobs SET match_score = ?, status = ? WHERE id = ?",
            (score.model_dump_json(), JobStatus.SCORED.value, job_id),
        )
        await self._db.commit()

    async def update_job_status(self, job_id: int, status: JobStatus):
        applied_at = datetime.utcnow().isoformat() if status == JobStatus.APPLIED else None
        if applied_at:
            await self._db.execute(
                "UPDATE jobs SET status = ?, applied_at = ? WHERE id = ?",
                (status.value, applied_at, job_id),
            )
        else:
            await self._db.execute(
                "UPDATE jobs SET status = ? WHERE id = ?", (status.value, job_id)
            )
        await self._db.commit()

    async def get_top_matches(self, min_score: int = 70, limit: int = 20) -> list[Job]:
        async with self._db.execute(
            """SELECT * FROM jobs WHERE status IN (?, ?)
               AND json_extract(match_score, '$.overall_score') >= ?
               ORDER BY json_extract(match_score, '$.overall_score') DESC LIMIT ?""",
            (JobStatus.SCORED.value, JobStatus.NOTIFIED.value, min_score, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_job(row) for row in rows]

    async def get_jobs_by_status(self, status: JobStatus, limit: int = 50) -> list[Job]:
        async with self._db.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY discovered_at DESC LIMIT ?",
            (status.value, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_job(row) for row in rows]

    async def get_stats(self) -> dict:
        stats = {}
        for status in JobStatus:
            async with self._db.execute(
                "SELECT COUNT(*) FROM jobs WHERE status = ?", (status.value,)
            ) as cursor:
                row = await cursor.fetchone()
                stats[status.value] = row[0]
        async with self._db.execute("SELECT COUNT(*) FROM jobs") as cursor:
            row = await cursor.fetchone()
            stats["total"] = row[0]
        return stats

    def _row_to_job(self, row) -> Job:
        match_score = None
        if row["match_score"]:
            match_score = MatchScore.model_validate_json(row["match_score"])
        return Job(
            id=row["id"],
            title=row["title"],
            company=row["company"],
            location=row["location"],
            description=row["description"],
            url=row["url"],
            source=JobSource(row["source"]),
            salary_min=row["salary_min"],
            salary_max=row["salary_max"],
            salary_currency=row["salary_currency"],
            posted_date=datetime.fromisoformat(row["posted_date"]) if row["posted_date"] else None,
            tags=json.loads(row["tags"]) if row["tags"] else [],
            remote=bool(row["remote"]),
            experience_level=row["experience_level"],
            apply_url=row["apply_url"],
            status=JobStatus(row["status"]),
            match_score=match_score,
            discovered_at=datetime.fromisoformat(row["discovered_at"]),
            applied_at=datetime.fromisoformat(row["applied_at"]) if row["applied_at"] else None,
            fingerprint=row["fingerprint"],
        )
