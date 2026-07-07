# Dockerfile for CyberCase Framework RAG Service
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set Hugging Face cache directory
ENV HF_HOME=/app/model_cache

# 1. Install Heavy ML Dependencies First
COPY requirements-ml.txt ./requirements-ml.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements-ml.txt

# 2. Download and cache models (Requires ML deps)
COPY app/download_model.py /app/download_model.py
RUN python /app/download_model.py && rm /app/download_model.py

# 3. Install remaining API dependencies
COPY requirements.txt ./requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt


# Copy RAG service application code
COPY app ./app

# Expose RAG Service port
EXPOSE 8001

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
