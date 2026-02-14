FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for document processing
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libsm6 \
        libxrender1 \
        libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching)
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY kruppai/ kruppai/
COPY schema/ schema/
COPY knowledge/ knowledge/
COPY templates/ templates/

# Create default directories
RUN mkdir -p /root/.kruppai /root/KruppAI-Output

EXPOSE 8000

CMD ["uvicorn", "kruppai.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
