FROM python:3.8-slim

WORKDIR /app

# Install system dependencies for Celery, PostgreSQL, and tokenizers
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    build-essential \
    pkg-config \
    netcat-openbsd \
    python3-dev \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && rm -rf /var/lib/apt/lists/*

# Add Rust to PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy only requirements first for better caching
COPY requirements.txt .

# Configure pip for better reliability
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install all packages from requirements.txt
RUN pip install --no-cache-dir --timeout 300 -r requirements.txt

# Copy project files
COPY . .

# Make start script executable
RUN chmod +x ./start.sh || echo "No start.sh found, will create one"

# Create start.sh if it doesn't exist
RUN if [ ! -f ./start.sh ]; then \
    echo '#!/bin/bash' > ./start.sh && \
    echo 'python manage.py migrate --noinput' >> ./start.sh && \
    echo 'python manage.py collectstatic --noinput' >> ./start.sh && \
    echo 'exec gunicorn app.wsgi:application --bind 0.0.0.0:8000' >> ./start.sh && \
    chmod +x ./start.sh; \
    fi

# Create empty __init__ files to ensure modules are importable
RUN mkdir -p core && touch core/__init__.py

# Create staticfiles directory
RUN mkdir -p staticfiles

EXPOSE 8000

CMD ["./start.sh"]