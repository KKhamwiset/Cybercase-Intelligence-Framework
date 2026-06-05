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

# Copy requirements and install
COPY rag_service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
    torch torchvision torchaudio \
    && pip install --no-cache-dir -r requirements.txt

# Download and cache the embedding model
COPY rag_service/app/download_model.py /app/download_model.py
RUN python /app/download_model.py && rm /app/download_model.py

# Copy RAG service application code
COPY rag_service/app ./app

# Expose RAG Service port
EXPOSE 8001

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
