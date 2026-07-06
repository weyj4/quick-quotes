# ---- stage 1: build the workbench UI -------------------------------------
FROM node:22-slim AS ui
WORKDIR /build
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY ui/ .
RUN npm run build            # -> /build/dist

# ---- stage 2: the app -----------------------------------------------------
FROM python:3.12-slim
WORKDIR /app

# install the package first so source edits don't bust the dependency layer
COPY pyproject.toml README.md ./
COPY quickquotes/ quickquotes/
RUN pip install --no-cache-dir ".[api,gemini]"

COPY api/ api/
COPY --from=ui /build/dist ui/dist

# Cloud Run injects PORT (8080). api.main serves ui/dist at / and the API
# at /api/*. Single container, single process.
ENV PYTHONUNBUFFERED=1
CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}
