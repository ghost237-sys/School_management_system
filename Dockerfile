# Use official Python image
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set workdir
WORKDIR /app

# System deps for psycopg2, Pillow (if needed), and build tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       libpq-dev \
       curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (better layer caching)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Ensure static/media dirs exist
RUN mkdir -p /app/staticfiles /app/media

# Default Django settings module
ENV DJANGO_SETTINGS_MODULE=Analitica.settings

# Railway will provide PORT; set a default for local docker runs
ENV PORT=8000
EXPOSE 8000

# Start: collectstatic -> migrate -> gunicorn
CMD bash -lc "python manage.py collectstatic --noinput && \
              python manage.py migrate --noinput && \
              gunicorn Analitica.wsgi:application --workers=3 --timeout=120 --bind 0.0.0.0:${PORT} --log-file -"
