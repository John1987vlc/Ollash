FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# 🔥 CAMBIO CLAVE: sqlite3 + libsqlite3-dev incluidos
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    curl \
    iputils-ping \
    net-tools \
    nmap \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY requirements-dev.txt .

RUN pip install --upgrade pip


RUN pip install -r requirements.txt
RUN pip install -r requirements-dev.txt

COPY . .
