FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    curl \
    iputils-ping \
    net-tools \
    nmap \
    ca-certificates \
    sqlite3 \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY requirements-dev.txt .

RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install -r requirements-dev.txt

# Copy only the necessary files and directories
COPY backend /app/backend
COPY frontend /app/frontend
COPY prompts /app/prompts
COPY auto_agent.py .
COPY auto_benchmark.py .
COPY benchmark.py .
COPY run_agent.py .
COPY run_web.py .
COPY .env.example .

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import backend; print('ok')" || exit 1

CMD ["python", "run_web.py"]
