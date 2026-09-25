import yaml
from pathlib import Path
import logging

from job_hunter.models import UserProfile

logger = logging.getLogger(__name__)

DEFAULT_PROFILE_PATH = Path("profile.yaml")

def load_profile(path: Path = DEFAULT_PROFILE_PATH) -> UserProfile:
    if not path.exists():
        logger.warning(f"Profile not found at {path}, using defaults")
        return UserProfile()
    with open(path) as f:
        data = yaml.safe_load(f)
    profile = UserProfile(**data)
    logger.info(f"Loaded profile for: {profile.name}")
    return profile
