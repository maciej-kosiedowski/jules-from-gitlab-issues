FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv export --format requirements-txt > requirements.txt && pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# Uruchomienie jako moduł
CMD ["python", "-m", "src.main"]
