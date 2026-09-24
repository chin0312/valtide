"""Application settings, loaded from the repo-root .env.

Secrets never appear in source. Everything the backend needs comes through this
single Settings object so there is one place to audit configuration.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo-root .env, resolved from this file so it works regardless of CWD.
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    # OKX OnchainOS (NVDAx token market data)
    okx_api_key: str = ""
    okx_api_secret: str = ""
    okx_api_passphrase: str = ""

    # Reference under test: OKX X-Perp NVDA index (exchange v5 API, usually public).
    # Confirm the exact instId from the OKX Dev Day builder kit / X-Perp help page.
    okx_xperp_index_id: str = "NVDA-USD"

    # Alpaca (NVDA underlying — same source as James's training).
    # Free accounts must use feed="iex"; "sip" needs a paid data plan.
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    alpaca_feed: str = "iex"

    # DexScreener live NVDAx token price (no key). Set the contract address for a
    # precise lookup; leave blank to fall back to symbol search.
    dexscreener_nvdax_address: str = ""

    # X Layer publisher. The deployment manifest is the source of truth for
    # deployed addresses and IDs; non-empty env values are explicit overrides.
    xlayer_rpc_url: str | None = None
    xlayer_chain_id: int | None = None
    registry_address: str | None = None
    risk_guard_address: str | None = None
    demo_vault_address: str | None = None
    publisher_private_key: str | None = None
    publish_validity_seconds: int = 15 * 60
    publish_enabled: bool = False
    # Scheduler-owned delivery is independent from the explicit HTTP publish
    # route. Keep both disabled by default for local/test safety.
    auto_publish_enabled: bool = False
    deployment_manifest_path: Path = _ENV_FILE.parent / "deployments" / "xlayer-testnet.json"

    # P0.5 warmed live runtime. Disabled by default so local tests and one-shot
    # diagnostics never start a background network loop implicitly.
    live_scheduler_enabled: bool = False
    live_scheduler_asset: str = "NVDAx"
    valtide_state_db_path: Path = _ENV_FILE.parent / "data" / "runtime" / "valtide.sqlite3"
    historical_panel_path: Path = (
        _ENV_FILE.parent / "data" / "generated" / "nvdax_historical_5m.csv"
    )
    # Underlying current-measurement tolerance, kept near one canonical
    # five-minute bucket. Older underlying bars remain trusted anchors but are
    # not assimilated as if they were measurements for the current bucket. The
    # reference under test needs no such tolerance: it is the confirmed OKX index
    # candle for the exact valued bar (ts == observation_ts, age 0).
    live_underlying_max_age_seconds: int = 6 * 60

    # CORS origins allowed to call the API from a browser (Valerie's Next.js app).
    # Comma-separated in the env var, e.g. "http://localhost:3000,https://valtide.app"
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def resolved_state_db_path(self) -> Path:
        path = self.valtide_state_db_path
        return path if path.is_absolute() else _ENV_FILE.parent / path

    @property
    def resolved_historical_panel_path(self) -> Path:
        path = self.historical_panel_path
        return path if path.is_absolute() else _ENV_FILE.parent / path

    @property
    def resolved_deployment_manifest_path(self) -> Path:
        path = self.deployment_manifest_path
        return path if path.is_absolute() else _ENV_FILE.parent / path


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so the .env is parsed once per process."""
    return Settings()
