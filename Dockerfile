# ---------- Stage 1: build (uses uv, but the system Python 3.13) ----------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

LABEL author="Ritik Sharma"

# Tell uv to NOT download a managed Python; use system python3.13 in the image
ENV UV_PYTHON_DOWNLOADS=0
# Optional but nice for cache mounts; not required
ENV UV_LINK_MODE=copy

WORKDIR /app

# Install only transitive deps first for better layer caching
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Now add the project and install it into the already-created env
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# (optional) compile .pyc in the builder
RUN /app/.venv/bin/python -m compileall -q /app


# ---------- Stage 2: runtime (NO uv; same system Python 3.13) ----------
FROM python:3.13-slim-bookworm AS runtime

LABEL author="Ritik Sharma"

WORKDIR /app

# Install required system packages for psycopg/libpq
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Put the project venv first on PATH
ENV PATH="/app/.venv/bin:${PATH}"

# Copy the built app + its venv
COPY --from=builder /app /app

# Start your app using the venv's Python (no uv needed in final image)
CMD ["python", "main.py"]
