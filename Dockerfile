# Use official slim Python image
FROM python:3.12-slim

# System packages for PostgreSQL, Redis, and static file handling
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


# Create non-root user for Celery and app
RUN addgroup --system celerygroup && \
    adduser --system --ingroup celerygroup celeryuser

# Set workdir
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Copy requirements and install
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy the project
COPY . /app/

# Ensure ownership for non-root execution
RUN chown -R celeryuser:celerygroup /app

# Set non-root user for container
USER celeryuser

# Expose Django default port
EXPOSE 8000

# Entrypoint can be overridden in docker-compose
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

