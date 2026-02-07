# Use an official Python runtime as a parent image
FROM python:3.10-slim-bullseye

# Set the working directory in the container
WORKDIR /app

# Install system dependencies needed for some Python packages (e.g., git, build-essential for some native extensions)
# Update package list and install git, build-essential
RUN apt-get update && apt-get install -y --no-install-recommends git build-essential curl iputils-ping net-tools nmap && rm -rf /var/lib/apt/lists/*

# Copy the requirements files into the container
COPY requirements.txt .
COPY requirements-dev.txt .

# Install any needed Python packages specified in requirements.txt and requirements-dev.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-dev.txt

# Copy the rest of the application code into the container
COPY . .

# Ensure Python output is unbuffered
ENV PYTHONUNBUFFERED 1

# Expose ports if your agent or benchmark needs to be accessed externally (e.g., if you run Ollama inside a separate container and access it this way, or for any web UI)
# For now, we assume Ollama is external, but keeping this in mind.
# EXPOSE 11434 

# Define environment variables or default arguments for running the agent/benchmark
# Default command to run if no other command is specified
# CMD ["python", "run_agent.py"]
