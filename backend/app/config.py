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
    cred1_path: Path
    google_client_id: str
    google_client_secret: str
    jwt_secret: str
    jwt_expires_minutes: int
    refresh_token_expire_days: int
    daily_check_limit: int
    rate_limit_window_seconds: int
    analyze_rate_limit_per_minute: int
    analyze_ip_rate_limit_per_minute: int
    auth_rate_limit_per_minute: int
    public_rate_limit_per_minute: int


@lru_cache
def get_settings() -> Settings:
    root = Path(__file__).resolve().parents[2]
    return Settings(
        environment=os.getenv("APP_ENV", "development"),
        database_url=os.getenv("DATABASE_URL", "postgresql://username:password@localhost:5432/fake_news_db"),
        qdrant_host=os.getenv("QDRANT_HOST", "localhost"),
        qdrant_port=int(os.getenv("QDRANT_PORT", "6333")),
        similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.92")),
        cred1_path=Path(os.getenv("CRED1_PATH", root / "data" / "cred1_compact.json")),
        google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
        jwt_secret=os.getenv("JWT_SECRET", ""),
        jwt_expires_minutes=int(os.getenv("JWT_EXPIRES_MINUTES", "60")),
        refresh_token_expire_days=int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30")),
        daily_check_limit=int(os.getenv("DAILY_CHECK_LIMIT", "5")),
        rate_limit_window_seconds=int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
        analyze_rate_limit_per_minute=int(os.getenv("ANALYZE_RATE_LIMIT_PER_MINUTE", "3")),
        analyze_ip_rate_limit_per_minute=int(os.getenv("ANALYZE_IP_RATE_LIMIT_PER_MINUTE", "10")),
        auth_rate_limit_per_minute=int(os.getenv("AUTH_RATE_LIMIT_PER_MINUTE", "10")),
        public_rate_limit_per_minute=int(os.getenv("PUBLIC_RATE_LIMIT_PER_MINUTE", "30")),
    )
