FROM python:3.12-slim

# -----------------------------
#   Build args / envs
# -----------------------------
ARG INSTALL_CHROMIUM=true
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV CHROME_VERSION=120.0.6099.71

# -----------------------------
#   System dependencies
# -----------------------------
RUN apt-get update && apt-get install -y \
    curl unzip gnupg wget \
    fonts-liberation libnss3 libxss1 libappindicator3-1 libasound2 \
    libatk-bridge2.0-0 libgtk-3-0 libpq-dev \
    gcc libssl-dev libffi-dev libjpeg-dev zlib1g-dev \
    netcat-openbsd git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# -----------------------------
#   Optional Chromium/Driver install
# -----------------------------
RUN if [ "$INSTALL_CHROMIUM" = "true" ]; then \
        apt-get update && \
        apt-get install -y chromium chromium-driver && \
        apt-get clean && rm -rf /var/lib/apt/lists/*; \
    fi

# -----------------------------
#   Add non-root user
# -----------------------------
RUN addgroup --system celerygroup && \
    adduser --system --ingroup celerygroup celeryuser

# -----------------------------
#   Setup working dir and install deps
# -----------------------------
WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . /app/

# -----------------------------
#   Permissions
# -----------------------------
RUN chown -R celeryuser:celerygroup \
    /app/haunt_ops /app/thia /app/manage.py /app/requirements.txt \
    /app/entrypoint.sh /app/Makefile || true

RUN mkdir -p /app/staticfiles /app/media /app/thia/logs && \
    chown -R celeryuser:celerygroup /app/staticfiles /app/media /app/thia/logs

USER celeryuser

# -----------------------------
#   Django runtime
# -----------------------------
EXPOSE 8000

# ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
