FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    curl \
    netcat-openbsd \
    libssl-dev \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN addgroup --system celerygroup && \
    adduser --system --ingroup celerygroup celeryuser

# Set working directory
WORKDIR /app

# Python environment settings
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . /app/

# Set ownership
RUN chown -R celeryuser:celerygroup /app

# Use non-root user
USER celeryuser

# Expose Django port
EXPOSE 8000

# Default entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
