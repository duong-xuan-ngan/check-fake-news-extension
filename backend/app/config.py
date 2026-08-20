from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    qdrant_host: str
    qdrant_port: int
    similarity_threshold: float
    mbfc_credibility_path: Path
    google_client_id: str
    google_client_secret: str
    jwt_secret: str
    jwt_expires_minutes: int
    refresh_token_expire_days: int
    daily_check_limit: int


@lru_cache
def get_settings() -> Settings:
    root = Path(__file__).resolve().parents[2]
    return Settings(
        environment=os.getenv("APP_ENV", "development"),
        database_url=os.getenv("DATABASE_URL", "postgresql://username:password@localhost:5432/fake_news_db"),
        qdrant_host=os.getenv("QDRANT_HOST", "localhost"),
        qdrant_port=int(os.getenv("QDRANT_PORT", "6333")),
        similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.92")),
        mbfc_credibility_path=Path(os.getenv("MBFC_CREDIBILITY_PATH", root.parent / "data" / "mbfc_credibility.json")),
        google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
        jwt_secret=os.getenv("JWT_SECRET", ""),
        jwt_expires_minutes=int(os.getenv("JWT_EXPIRES_MINUTES", "60")),
        refresh_token_expire_days=int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30")),
        daily_check_limit=int(os.getenv("DAILY_CHECK_LIMIT", "5")),
    )
