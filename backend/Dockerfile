# Production-ready Dockerfile for CyberCase Framework FastAPI Backend
# Using ./backend context for build
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt ./requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy backend application code
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

# Expose FastAPI port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
