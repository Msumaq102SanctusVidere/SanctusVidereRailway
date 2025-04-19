# Start with a Python base image
FROM python:3.9-slim

# Set working directory in the container
WORKDIR /app

# Install system dependencies required for PDF processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file first (for better caching)
COPY requirements.txt .

# Install Python dependencies including Flask
RUN pip install --no-cache-dir -r requirements.txt

# Create required directories with proper permissions
RUN mkdir -p /app/tiles_output && \
    mkdir -p /app/memory_store && \
    mkdir -p /app/uploads && \
    chmod -R 777 /app/tiles_output && \
    chmod -R 777 /app/memory_store && \
    chmod -R 777 /app/uploads

# Copy all application files
COPY . .

# Expose port for the API
EXPOSE 8080

# Command to run when the container starts
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "api:app"]
