FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt . 2>/dev/null || true
RUN python -m pip install --upgrade pip && if [ -f requirements.txt ]; then pip install -r requirements.txt; else pip install django psycopg[binary] python-dotenv; fi
COPY . /app
EXPOSE 8000
