from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/clairvoyance"
    ESPN_MLB_BASE: str = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb"
    ESPN_NHL_BASE: str = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl"
    NHL_EDGE_BASE: str = "https://api.nhle.com/stats/rest/en"
    MONEYPUCK_TEAMS_URL: str = "https://moneypuck.com/teams.htm"
    NHL_SEASON: str = "20252026"
    NHL_GAME_TYPE: int = 3
    TIMEZONE: str = "America/Denver"
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env"}


settings = Settings()
