FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEPLOYMENT_MANIFEST_PATH=/app/deployments/xlayer-testnet.json \
    HISTORICAL_PANEL_PATH=/app/data/generated/nvdax_historical_5m.csv

WORKDIR /app

COPY . .

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir ./valtide-quant-service-p1ac \
    && python -m pip install --no-cache-dir ./apps/api

# Shell form is intentional so Railway's PORT environment variable expands.
# Keep one process: the application owns the single live scheduler lifecycle.
CMD uvicorn valtide_api.main:app --host 0.0.0.0 --port ${PORT:-8000}
