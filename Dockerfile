# syntax=docker/dockerfile:1

# ── Stage 1: Builder ──────────────────────────────────────────────
FROM python:3.13-slim-bookworm AS builder

WORKDIR /app

# Install build dependencies for compiling wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies into a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -e .

# ── Stage 2: Production ───────────────────────────────────────────
FROM python:3.13-slim-bookworm AS production

WORKDIR /app

# Create non-root user
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -m -s /bin/bash appuser

# Copy the virtual environment from builder
COPY --from=builder --chown=appuser:appgroup /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

# Expose application port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

USER appuser

# Start the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
