# Use Python 3.12 slim image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_SYSTEM_PYTHON=1
ENV VIRTUAL_ENV=/app/.venv

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv and the application virtual environment to PATH
ENV PATH="/app/.venv/bin:/root/.local/bin:$PATH"

# Set work directory
WORKDIR /app

# Copy project metadata
COPY pyproject.toml uv.lock README.md ./
COPY .env.example .env.example

# Install dependencies using uv
RUN uv sync --no-dev --no-install-project

# Copy application code
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY scripts ./scripts

# Install the project after source files are available
RUN uv sync --no-dev

# Create non-root user for security
RUN chmod +x /app/scripts/docker-entrypoint.sh \
    && useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run migrations, then the application
CMD ["/app/scripts/docker-entrypoint.sh"]
