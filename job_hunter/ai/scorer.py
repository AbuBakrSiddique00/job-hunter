import json
import logging
import asyncio
from typing import Optional
from google import genai
from google.genai import types

from job_hunter.config import settings
from job_hunter.models import Job, UserProfile, MatchScore

logger = logging.getLogger(__name__)


class JobScorer:
    def __init__(self, profile: UserProfile):
        self.profile = profile
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.gemini_model or "gemini-2.5-flash"
        self._semaphore = asyncio.Semaphore(10)  # max 10 concurrent requests
        self._rate_lock = asyncio.Lock()
        self._last_request_time = 0.0
        self._min_interval = 6.0  # ~10 req/min

    async def _wait_for_rate_limit(self):
        async with self._rate_lock:
            loop = asyncio.get_event_loop()
            now = loop.time()
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request_time = loop.time()

    def _build_prompt(self, job: Job) -> str:
        return f"""Analyze the following job description against the candidate profile and score the match.

## Candidate Profile
- **Name:** {self.profile.name}
- **Target Titles:** {', '.join(self.profile.target_titles)}
- **Skills:** {', '.join(self.profile.skills)}
- **Experience:** {self.profile.experience_years} years
- **Education:** {self.profile.education}
- **Remote Only:** {self.profile.remote_only}
- **Min Salary:** {self.profile.min_salary or 'Not specified'}
- **Bio:** {self.profile.bio}

## Job Details
- **Title:** {job.title}
- **Company:** {job.company}
- **Location:** {job.location}
- **Remote:** {job.remote}
- **Salary Range:** {job.salary_min or '?'} - {job.salary_max or '?'} {job.salary_currency}
- **Description:**
{job.description[:4000]}

## Instructions
Evaluate skill overlap, experience match, title relevance, salary compatibility, location/remote match, and culture indicators.
Generate 3-5 tailored cover letter bullet points that connect the candidate's background to this specific role.
Be honest and critical in your scoring — don't inflate scores."""

    async def score_job(self, job: Job, retries: int = 3) -> Optional[MatchScore]:
        """Score a job against the user profile using Gemini."""
        prompt = self._build_prompt(job)

        for attempt in range(retries):
            try:
                await self._wait_for_rate_limit()

                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=MatchScore,
                        temperature=0.3,
                    ),
                )

                output_text = response.text
                if not output_text:
                    logger.error(f"Empty response from Gemini for job {job.id}")
                    continue

                data = json.loads(output_text)
                score = MatchScore(**data)
                logger.info(
                    f"Scored job {job.id} ({job.title} @ {job.company}): {score.overall_score}/100"
                )
                return score

            except json.JSONDecodeError as e:
                logger.warning(
                    f"JSON parse error for job {job.id} (attempt {attempt + 1}): {e}"
                )
                await asyncio.sleep(2**attempt)
            except Exception as e:
                logger.warning(
                    f"Error scoring job {job.id} (attempt {attempt + 1}/{retries}): {e}"
                )
                await asyncio.sleep(2**attempt)

        logger.error(f"Failed to score job {job.id} after {retries} attempts.")
        return None

    async def generate_cover_letter(self, job: Job) -> str:
        """Generate a full cover letter for a specific job."""
        prompt = f"""Write a concise, compelling cover letter for the following candidate applying to this job.
Keep it to 3 short paragraphs. Be specific — reference the company by name and connect the candidate's actual skills to the job requirements.

## Candidate
- Name: {self.profile.name}
- Skills: {', '.join(self.profile.skills)}
- Experience: {self.profile.experience_years} years
- Bio: {self.profile.bio}

## Job
- Title: {job.title}
- Company: {job.company}
- Description:
{job.description[:3000]}
"""
        try:
            await self._wait_for_rate_limit()
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.7),
            )
            return response.text or "Could not generate cover letter."
        except Exception as e:
            logger.error(f"Cover letter generation failed: {e}")
            return f"Error generating cover letter: {e}"
