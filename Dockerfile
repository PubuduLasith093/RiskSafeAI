# Use official Python image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set workdir
WORKDIR /app

# Install OS dependencies
RUN apt-get update && apt-get install -y build-essential poppler-utils curl && rm -rf /var/lib/apt/lists/*

# Install uv (Python package/dependency manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"
ENV UV_LINK_MODE=copy
ENV PYTHONPATH="/app:/app/compliance_chat"

# Copy dependency manifests for better layer caching
COPY requirements.txt ./

# Install dependencies into the system interpreter using uv pip
RUN uv pip install --system -r requirements.txt && \
    pip uninstall -y pinecone-plugin-inference || true

# Pre-download NLTK data to avoid runtime downloads
RUN python -m nltk.downloader -d /usr/local/share/nltk_data punkt punkt_tab

# Copy project files
COPY . .


# Expose port (aligned with main.py)
EXPOSE 8000

# Run FastAPI with Gunicorn + uvicorn workers for concurrent request handling
# 2 workers allows health checks to be served while long requests process
# Timeout set to 600s (10 min) for complex compliance workflows that take 3-5 minutes
CMD ["gunicorn", "main:app", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "--timeout", "600", "--keep-alive", "300", "--graceful-timeout", "600"]
