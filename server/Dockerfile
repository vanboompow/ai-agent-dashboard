# Multi-stage build for optimized production image
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libc6-dev \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Development stage
FROM base AS development

# Copy requirements
COPY requirements.txt .

# Install Python dependencies (including dev dependencies)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for development
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Expose port
EXPOSE 8000

# Development command with reload
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production build stage
FROM base AS builder

# Copy requirements
COPY requirements.txt .

# Install build dependencies and Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    && pip install --user --no-cache-dir -r requirements.txt \
    && apt-get remove -y build-essential \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Production stage
FROM base AS production

# Build arguments for metadata
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION

# Add metadata labels
LABEL org.opencontainers.image.title="AI Agent Dashboard Backend" \
      org.opencontainers.image.description="FastAPI backend for AI Agent Dashboard" \
      org.opencontainers.image.created=$BUILD_DATE \
      org.opencontainers.image.revision=$VCS_REF \
      org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.source="https://github.com/your-org/ai-agent-dashboard" \
      org.opencontainers.image.licenses="MIT"

# Copy Python packages from builder stage
COPY --from=builder /root/.local /usr/local

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Expose port
EXPOSE 8000

# Production command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# Testing stage
FROM development AS testing

# Install additional test dependencies
RUN pip install --no-cache-dir pytest-xvfb

# Copy test files
COPY tests/ ./tests/

# Run tests
RUN python -m pytest tests/ -v --cov=app --cov-report=term-missing

# Default to production stage
FROM production AS final