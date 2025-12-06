FROM python:3.12-slim

# Install system dependencies
# Install Chromium and matching ChromeDriver for ARM or x86
RUN apt-get update && \
    apt-get install -y curl unzip gnupg wget fonts-liberation libnss3 libxss1 \
    libappindicator3-1 libasound2 libatk-bridge2.0-0 libgtk-3-0 libpq-dev \
    gcc libssl-dev libffi-dev libjpeg-dev zlib1g-dev netcat-openbsd git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Chromium manually (pin version for stability)
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then \
        CHROME_URL="https://storage.googleapis.com/chrome-for-testing-public/114.0.5735.90/linux64/chrome-linux64.zip"; \
        DRIVER_URL="https://storage.googleapis.com/chrome-for-testing-public/114.0.5735.90/linux64/chromedriver-linux64.zip"; \
    else \
        CHROME_URL="https://storage.googleapis.com/chrome-for-testing-public/114.0.5735.90/linux-arm64/chrome-linux-arm64.zip"; \
        DRIVER_URL="https://storage.googleapis.com/chrome-for-testing-public/114.0.5735.90/linux-arm64/chromedriver-linux-arm64.zip"; \
    fi && \
    mkdir -p /opt/chrome && \
    curl -sSL "$CHROME_URL" -o chrome.zip && \
    unzip chrome.zip -d /opt/chrome && \
    ln -s /opt/chrome/chrome-*/chrome /usr/bin/chromium && \
    curl -sSL "$DRIVER_URL" -o chromedriver.zip && \
    unzip chromedriver.zip -d /usr/local/bin && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -f chrome.zip chromedriver.zip


# Create non-root user
RUN addgroup --system celerygroup && \
    adduser --system --ingroup celerygroup celeryuser

# Set workdir
WORKDIR /app

# Env vars
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Install Python deps
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . /app/

# Set ownership of necessary paths
RUN chown -R celeryuser:celerygroup \
    /app/haunt_ops \
    /app/thia \
    /app/manage.py \
    /app/requirements.txt \
    /app/entrypoint.sh \
    /app/Makefile || true

# Pre-create writable directories
RUN mkdir -p /app/staticfiles /app/media /app/thia/logs && \
    chown -R celeryuser:celerygroup /app/staticfiles /app/media /app/thia/logs

# Switch to non-root
USER celeryuser

# Expose Django port
EXPOSE 8000

# Default command (if you prefer running without overriding in docker-compose)
# ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
