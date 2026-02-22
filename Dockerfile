# Stage 1: Builder
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsqlite3-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
COPY requirements-dev.txt .

# Install dependencies into a virtual environment or specific path
# This keeps the final image cleaner
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-dev.txt

# Stage 2: Runtime
FROM python:3.11-slim-bookworm AS runtime

WORKDIR /app

# Install only necessary runtime system tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    iputils-ping \
    nmap \
    ca-certificates \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Copy application code
# Ordered from least to most likely to change
COPY backend /app/backend
COPY frontend /app/frontend
COPY legacy /app/legacy
COPY docs /app/docs
COPY *.py /app/
COPY .env.example /app/.env.example
COPY Makefile /app/Makefile

# Create persistent storage directory
RUN mkdir -p /app/.ollash && chmod 777 /app/.ollash

# Expose the Flask port
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || python -c "import backend; print('ok')"

CMD ["python", "run_web.py"]
