# Use Python 3.8.10 slim base image
FROM python:3.8.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port for Django
EXPOSE 8000

# Default command (overridden by Render's dockerCommand)
CMD ["gunicorn", "app.wsgi:application", "--bind", "0.0.0.0:8000"]