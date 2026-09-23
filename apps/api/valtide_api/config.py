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

    # X Layer publisher (Phase 3 — not required for Phase 1/2)
    xlayer_rpc_url: str | None = None
    publisher_private_key: str | None = None

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


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so the .env is parsed once per process."""
    return Settings()
