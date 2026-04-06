from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./dev.db"
    CURRENT_SEASON: int = 2026
    HISTORICAL_SEASONS: list[int] = Field(default_factory=lambda: [2023, 2024, 2025])
    DEFAULT_LEAGUE_SIZE: int = 12
    DEFAULT_SCORING_FORMAT: str = "ppr"
    ROSTER_SLOTS: dict[str, int] = Field(
        default_factory=lambda: {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1}
    )
    REPLACEMENT_BUFFER: int = 2
    FANTASYPROS_ADP_URL: str = "https://www.fantasypros.com/nfl/adp/overall.php"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
