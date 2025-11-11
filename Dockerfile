# Base Python image
FROM python:3.12-slim

# Install system dependencies, including Chromium
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    unzip \
    wget \
    chromium \
    chromium-driver \
    build-essential \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libpq-dev \
    gcc \
    libssl-dev \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN addgroup --system celerygroup && \
    adduser --system --ingroup celerygroup celeryuser

# Set workdir
WORKDIR /app

# Environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install Python requirements
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Change ownership
RUN chown -R celeryuser:celerygroup /app

# Set non-root user
USER celeryuser

# Set Chrome binary env (needed for Selenium)
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Expose Django port
EXPOSE 8000

# Default command
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
