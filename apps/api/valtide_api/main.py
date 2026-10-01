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
from valtide_api.routes import assets, backtest, history, onchain, publish, runtime, valuation
from valtide_api.routes import replay as replay_route
from valtide_api.runtime_store import RuntimeStateIntegrityError, get_runtime_store
from valtide_api.scheduler import build_enabled_schedulers

logger = logging.getLogger("valtide")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Restore durable live state and optionally start the live scheduler."""
    runtime_store = get_runtime_store()
    schedulers = build_enabled_schedulers(settings, runtime_store)
    # Preserve the legacy single-asset restore even when scheduling is disabled.
    # If explicit asset workers are added later, restore each under its own key.
    restore_assets = dict.fromkeys(
        (settings.live_scheduler_asset, *(worker.asset for worker in schedulers))
    )
    for asset in restore_assets:
        try:
            record = runtime_store.load_runtime(asset)
            if record is not None:
                if record.state is not None:
                    state_store.save_state(asset, record.state)
                if record.latest_result is not None:
                    state_store.save_latest_result(asset, record.latest_result)
                logger.info(
                    "Restored live runtime asset=%s state=%s result=%s",
                    asset,
                    record.state is not None,
                    record.latest_result is not None,
                )
        except RuntimeStateIntegrityError:
            logger.exception(
                "Persisted runtime state is invalid for asset=%s; scheduler remains "
                "available but the next tick must repair the state explicitly",
                asset,
            )

    for scheduler in schedulers:
        await scheduler.start()
        logger.info("Live scheduler enabled for asset=%s", scheduler.asset)
    try:
        yield
    finally:
        for scheduler in schedulers:
            await scheduler.stop()


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
    expose_headers=["X-Valtide-Source"],
)

app.include_router(assets.router)
app.include_router(valuation.router)
app.include_router(replay_route.router)
app.include_router(backtest.router)
app.include_router(history.router)
app.include_router(publish.router)
app.include_router(onchain.router)
app.include_router(runtime.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}
