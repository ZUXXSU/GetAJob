FROM python:3.12-slim

# Install Node.js for Gemini CLI + Playwright dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates git \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @google/gemini-cli \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (chromium only — saves space)
RUN python -m playwright install chromium

# App code
COPY backend/ backend/
COPY frontend/ frontend/
COPY .env.example .

# Runtime data dir
RUN mkdir -p data/resumes data/backups data/linkedin_session

ENV GEMINI_BIN=/usr/bin/gemini
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

WORKDIR /app/backend
CMD ["python", "main.py"]
