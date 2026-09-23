"""FastAPI application entry point.

Wires CORS (so Valerie's browser app can call the API) and includes the route
routers. Run locally with:

    uvicorn valtide_api.main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from valtide_api import state_store
from valtide_api.config import get_settings
from valtide_api.data_source import resolve_snapshots
from valtide_api.replay import replay
from valtide_api.routes import assets, backtest, publish, valuation
from valtide_api.routes import replay as replay_route

logger = logging.getLogger("valtide")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Seed the cache with the latest result on startup, so /api/valuation

    serves a real (model-computed) result out of the box. Uses James's panel if
    present in data/sample/, otherwise the scripted scenario.
    """
    try:
        snapshots, source = resolve_snapshots()
        results = replay(snapshots)
        if results:
            state_store.save_latest_result("NVDAx", results[-1])
            logger.info(
                "Seeded NVDAx from %s: %s (%d steps)",
                source,
                results[-1].evidence_state,
                len(results),
            )
    except Exception:  # noqa: BLE001 - startup must not crash the app
        logger.exception(
            "Seed failed; /api/valuation will return 503 until a real or scenario "
            "result is available"
        )
    yield


app = FastAPI(
    title="Valtide API",
    version="0.1.0",
    description="Orchestration & API layer for tokenized-equity collateral validation.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assets.router)
app.include_router(valuation.router)
app.include_router(replay_route.router)
app.include_router(backtest.router)
app.include_router(publish.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}
