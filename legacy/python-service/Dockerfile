FROM python:3.12-slim

# System deps for sentence-transformers + lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download sentence-transformers model (optional, ~2.5GB)
# Comment out if you want to download on first run instead
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-large')" || echo "Model download skipped (will download on first run)"

# Copy source
COPY bettersaul_sources/ ./bettersaul_sources/
COPY scripts/ ./scripts/

EXPOSE 8001

CMD ["uvicorn", "bettersaul_sources.api:app", "--host", "0.0.0.0", "--port", "8001"]
