FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
COPY automation/requirements-api.txt ./automation/
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r automation/requirements-api.txt

# Copy application code
COPY . .

# Create cache directory
RUN mkdir -p /app/cache

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=automation/api_wrapper.py

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Run the application
CMD ["python", "automation/api_wrapper.py"]