FROM python:3.11-slim

WORKDIR /app

# NLTK data used by sumy tokenizer fallback (TextRank).
ENV NLTK_DATA=/usr/local/nltk_data

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download NLTK punkt so extractive summarization works in minimal containers.
RUN python -c "import nltk; nltk.download('punkt', download_dir='${NLTK_DATA}', quiet=True)"

# Copy application code
COPY app /app/app
COPY tests /app/tests
COPY run_migrations.py /app/

# Expose port (informational; platform will map $PORT)
EXPOSE 8000

# Run application on the port provided by the platform (default 8000)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
