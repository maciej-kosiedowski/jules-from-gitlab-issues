FROM python:3.12-slim

WORKDIR /app

# Create a non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends     git     && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv export --format requirements-txt > requirements.txt && pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Create necessary directories and set permissions
RUN mkdir -p /app/logs /app/data &&     chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Uruchomienie jako moduł
CMD ["python", "-m", "src.main"]
