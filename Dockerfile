# Use Python 3.11 as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install additional dependencies for FastAPI
RUN pip install --no-cache-dir uvicorn[standard] fastapi

# Copy application code
COPY src/ src/

# Create non-root user
RUN useradd -m -u 1000 appuser
RUN chown -R appuser:appuser /app
USER appuser

# Create necessary directories
RUN mkdir -p temp logs

# Set environment variables
ENV PYTHONPATH=/app
ENV TEMP_DIR=/app/temp
ENV LOGS_DIR=/app/logs

# Expose port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8080"]