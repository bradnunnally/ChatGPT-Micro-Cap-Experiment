from __future__ import annotations

from pathlib import Path
from typing import List, Optional

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
    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent)
    data_dir: Path | str = Field(default="data")

    # Files
    db_file: Path | str = Field(default="data/trading.db")
    portfolio_csv: Path | str = Field(default="data/chatgpt_portfolio_update.csv")
    trade_log_csv: Path | str = Field(default="data/chatgpt_trade_log.csv")
    watchlist_file: Path | str = Field(default="data/watchlist.json")

    # Misc
    cache_ttl_seconds: int = Field(default=300, ge=0)
    environment: str = Field(default="development")
    finnhub_api_key: str | None = Field(default=None, validation_alias="FINNHUB_API_KEY")
    use_micro_providers: bool | None = Field(
        default=None,
        description="Override auto provider selection. When True forces use of micro providers if available.",
        validation_alias="ENABLE_MICRO_PROVIDERS",
    )
    app_use_finnhub: bool | None = Field(
        default=None,
        description="Legacy flag to explicitly enable Finnhub path.",
        validation_alias="APP_USE_FINNHUB",
    )
    no_dev_seed: bool = Field(
        default=False,
        description="Disable automatic dev_stage seeding of synthetic portfolio.",
        validation_alias="NO_DEV_SEED",
    )
    # Trading calendar
    trading_holidays: List[str] = Field(
        default_factory=list, description="List of YYYY-MM-DD holiday dates when market is closed"
    )
    # Alert thresholds
    alert_drawdown_pct: float = Field(default=10.0, description="Trigger alert when drawdown exceeds this % (positive number)")
    alert_concentration_top1_pct: float = Field(default=40.0, description="Trigger alert when top1 concentration exceeds %")
    alert_var95_pct: float = Field(default=4.0, description="Trigger alert when 1-day 95% VaR exceeds % of equity")

    @field_validator(
        "data_dir", "db_file", "portfolio_csv", "trade_log_csv", "watchlist_file", mode="after"
    )
    @classmethod
    def resolve_paths(cls, v: Path | str, info: ValidationInfo) -> Path:
        base_dir: Path = info.data.get("base_dir")  # type: ignore[assignment]
        return _to_path(v, base=base_dir)

    @field_validator("finnhub_api_key")
    @classmethod
    def validate_key(cls, v: str | None) -> str | None:  # pragma: no cover - simple guard
        if v is None:
            return v
        if len(v.strip()) < 8:
            raise ValueError("FINNHUB_API_KEY appears too short")
        return v.strip()

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

    # Derived convenience flags (not environment backed directly)
    @property
    def micro_enabled(self) -> bool:
        """Return True if micro providers should be used based on explicit flags + environment.

        Order of precedence:
        1. Explicit use_micro_providers env var (ENABLE_MICRO_PROVIDERS)
        2. Legacy app_use_finnhub (APP_USE_FINNHUB)
        3. FINNHUB key present & environment == production
        4. dev_stage always allowed (synthetic provider)
        """
        if self.use_micro_providers is not None:
            return bool(self.use_micro_providers)
        if self.app_use_finnhub is not None:
            return bool(self.app_use_finnhub)
        if self.environment == "production" and self.finnhub_api_key:
            return True
        if self.environment == "dev_stage":
            return True
        return False


settings = Settings()
