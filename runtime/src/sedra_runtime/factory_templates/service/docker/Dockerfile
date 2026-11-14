# {{service_name}} Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/
COPY configs/ ./configs/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Expose port (adjust as needed)
EXPOSE 8000

# Run service
CMD ["python", "-m", "{{service_name}}"]