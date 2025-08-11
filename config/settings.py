from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _to_path(v: str | Path, base: Optional[Path] = None) -> Path:
    p = Path(v)
    if not p.is_absolute() and base:
        p = base / p
    return p


class Paths(BaseModel):
    base_dir: Path
    data_dir: Path
    db_file: Path
    portfolio_csv: Path
    trade_log_csv: Path
    watchlist_file: Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="APP_", extra="ignore"
    )

    # Core
    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    data_dir: Path | str = Field(default="data")

    # Files
    db_file: Path | str = Field(default="data/trading.db")
    portfolio_csv: Path | str = Field(default="data/chatgpt_portfolio_update.csv")
    trade_log_csv: Path | str = Field(default="data/chatgpt_trade_log.csv")
    watchlist_file: Path | str = Field(default="data/watchlist.json")

    # Misc
    cache_ttl_seconds: int = Field(default=300, ge=0)
    environment: str = Field(default="development")

    # Normalize path-like envs relative to base_dir
    @field_validator(
        "data_dir", "db_file", "portfolio_csv", "trade_log_csv", "watchlist_file", mode="after"
    )
    @classmethod
    def resolve_paths(cls, v: Path | str, info: ValidationInfo) -> Path:
        base_dir: Path = info.data.get("base_dir")  # type: ignore[assignment]
        return _to_path(v, base=base_dir)

    @property
    def paths(self) -> Paths:
        return Paths(
            base_dir=self.base_dir,
            data_dir=Path(self.data_dir),
            db_file=Path(self.db_file),
            portfolio_csv=Path(self.portfolio_csv),
            trade_log_csv=Path(self.trade_log_csv),
            watchlist_file=Path(self.watchlist_file),
        )


# Singleton settings instance
settings = Settings()
