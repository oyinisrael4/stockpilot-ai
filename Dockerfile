FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build && npm run build:showcase

FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=10000
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements-base.txt backend/requirements-cloud.txt backend/
RUN pip install --no-cache-dir -r backend/requirements-cloud.txt \
    && useradd --create-home stockpilot
COPY backend/ backend/
COPY scripts/render_start.py scripts/render_start.py
COPY --from=frontend /build/frontend/dist frontend/dist
COPY --from=frontend /build/frontend/dist-showcase frontend/dist-showcase
USER stockpilot
EXPOSE 10000
CMD ["python", "scripts/render_start.py"]
