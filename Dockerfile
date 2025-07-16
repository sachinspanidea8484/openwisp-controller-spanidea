# Multi-stage build for production
FROM python:3.11-bullseye AS base

# Install system dependencies including WeasyPrint dependencies
RUN apt-get update && \
    apt-get install --yes \
    # Basic dependencies
    zlib1g-dev \
    libjpeg-dev \
    gdal-bin \
    libproj-dev \
    libgeos-dev \
    libspatialite-dev \
    libsqlite3-mod-spatialite \
    sqlite3 \
    libsqlite3-dev \
    openssl \
    libssl-dev \
    gcc \
    g++ \
    netcat \
    fping \
    # WeasyPrint and PDF generation dependencies
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-3.0 \
    libgirepository1.0-dev \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf2.0-dev \
    libffi-dev \
    shared-mime-info \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create openwisp user
RUN useradd -m -d /opt/openwisp -s /bin/bash openwisp

WORKDIR /opt/openwisp

# Copy requirements files first for better caching
COPY requirements-test.txt requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-test.txt && \
    pip install --no-cache-dir redis gunicorn watchdog

# Install SMS dependencies with compatible Twilio version
# Twilio 6.x has TwilioRestClient, while 7.x+ uses Client
RUN pip install --no-cache-dir sendsms==0.2.0 django-sendsms==0.5 twilio==6.63.2

# Copy entire project including local modules
COPY --chown=openwisp:openwisp . /opt/openwisp/

# Ensure the local modules are in Python path
ENV PYTHONPATH=/opt/openwisp:$PYTHONPATH

# Install the application in development mode to use local modules
RUN pip install --no-cache-dir -e /opt/openwisp

# Switch to non-root user
USER openwisp

WORKDIR /opt/openwisp/tests/

ENV NAME=openwisp-controller \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/opt/openwisp:/opt/openwisp/tests:$PYTHONPATH

CMD ["sh", "docker-entrypoint.sh"]
EXPOSE 8000