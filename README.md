# OpenWISP Controller

OpenWISP Controller is an open-source network management system for OpenWrt-based devices. This repository contains a Dockerized setup that extends the upstream OpenWISP Controller with a custom **Test Management** module, enabling test case execution, scheduling, and result tracking through integration with the Test Executor service.

---

## What This Setup Provides

- Centralized device management via web interface and REST API
- Configuration management and diff tracking for network devices
- IP address management, certificate handling, and location tracking
- Background task scheduling via Celery
- Time-series metrics storage with InfluxDB
- Test Management module for triggering and tracking automated test executions on managed devices

---

## Project Structure

```
.
├── Dockerfile                      # Multi-stage image build (Python 3.11 + WeasyPrint + GIS libs)
├── docker-compose.yml              # Service orchestration
├── requirements.txt                # Python dependencies
├── requirements-test.txt           # Additional test/dev dependencies
├── example.env                     # Template — copy to .env and fill in values
├── .env                            # Your local environment config (never commit this)
├── tests/
│   ├── docker-entrypoint.sh        # Container startup script
│   ├── openwisp2/                  # Django project settings and config
│   └── influxdb.conf               # InfluxDB configuration
├── nginx/
│   └── openwisp.conf               # Nginx reverse proxy configuration
├── media/                          # User-uploaded files (firmware, attachments)
├── logs/
│   ├── nginx/                      # Nginx access and error logs
│   └── ...                         # Application logs
└── README.md
```

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) v28 or later
- [Docker Compose](https://docs.docker.com/compose/install/) v2.20 or later

Verify your installed versions:

```bash
docker --version
docker compose version
```

---

## Configuration

### 1. Create your `.env` file

```bash
cp example.env .env
```

Then open `.env` and fill in values for your environment. Never commit `.env` to version control.

### Key Settings

#### Application

```env
APP_PORT=8000
DEBUG_MODE=False
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_LOG_LEVEL=INFO
DJANGO_LANGUAGE_CODE=en-gb
TIME_ZONE=Asia/Kolkata
ALLOWED_HOSTS=*
CORS_ORIGIN_ALLOW_ALL=True
```

#### Server Endpoints

Update these based on your deployment environment:

```env
# Local development
OPENWISP_SERVER_IP=http://172.17.0.1:8000
OPENWISP_CONTROLLER_API_HOST=http://172.17.0.1:8000
EXECUTOR_SERVER_IP=http://172.17.0.1:8080

# DEV environment (AWS)
# OPENWISP_SERVER_IP=http://54.234.248.241
# EXECUTOR_SERVER_IP=http://34.235.14.203
# OPENWISP_CONTROLLER_API_HOST=http://54.234.248.241

# UAT environment (AWS)
# OPENWISP_SERVER_IP=http://44.193.103.240
# EXECUTOR_SERVER_IP=http://44.199.94.165
# OPENWISP_CONTROLLER_API_HOST=http://44.193.103.240
```

`EXECUTOR_SERVER_IP` is the address of the Test Executor service. It must be reachable from the OpenWISP container at runtime.

#### Email (Gmail SMTP)

This project uses Gmail SMTP. You must use a **Google App Password**, not your regular Gmail password.

**How to generate a Gmail App Password:**
1. Go to your Google Account → [Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already enabled
3. Go to **App Passwords** (search for it in the Security page)
4. Select app: `Mail`, device: `Other` → give it a name (e.g. `openwisp`)
5. Copy the 16-character password generated

```env
EMAIL_HOST=<smtp_server_host>
EMAIL_PORT=<smtp_port>
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx   # 16-char App Password (spaces are fine)
```

#### Database

```env
DB_HOST=postgres
DB_PORT=5432
DB_USER=your-db-user
DB_PASS=your-db-password
DB_NAME=your-db-name
```

#### InfluxDB

```env
INFLUXDB_HOST=influxdb
INFLUXDB_PORT=8086
INFLUXDB_USER=your-influxdb-user
INFLUXDB_PASS=your-influxdb-password
INFLUXDB_NAME=your-influxdb-dbname
```

#### uWSGI

```env
UWSGI_PROCESSES=2
UWSGI_THREADS=2
UWSGI_LISTEN=100
```

---

## Services

The `docker-compose.yml` defines the following services:

| Service | Description |
|---|---|
| `controller` | Django application server (uWSGI), runs migrations and serves the API and admin UI |
| `celery-worker` | Handles asynchronous background tasks (test execution, notifications, etc.) |
| `celery-beat` | Schedules periodic tasks (result polling, health checks, etc.) |
| `postgres` | PostgreSQL 17 with PostGIS 3.5 extension for spatial data |
| `redis` | Message broker for Celery and application cache |
| `influxdb` | Time-series database for network metrics (InfluxDB 1.8) |
| `nginx` | Reverse proxy, serves static files and terminates HTTP/HTTPS traffic |

---

## Setup and Deployment

### 1. Clone and enter the project directory

```bash
cd openwisp-controller
```

### 2. Configure environment

```bash
cp example.env .env
```

Edit `.env` with the correct values for your target environment (local, DEV, or UAT). At minimum, set the correct `OPENWISP_SERVER_IP`, `OPENWISP_CONTROLLER_API_HOST`, and `EXECUTOR_SERVER_IP`.

### 3. Build and start all services

```bash
sudo docker compose up -d --build
```

This will build the application image, run database migrations via the entrypoint script, collect static files, and start all services.

### 4. Access the application

- Web UI: `http://<server-ip>`
- Admin panel: `http://<server-ip>/admin`

### 5. Default credentials

```
Username: admin
Email:    admin@example.com
Password: admin
```

---

## Firmware Hardware ID Configuration

Device-to-firmware board mappings are maintained in a single JSON file:

```
openwisp_firmware_upgrader/hardware_ids.json
```

This file is the only place you need to edit when adding a new device type. `hardware.py` and `settings.py` load it automatically at startup — no code changes needed.

### How to add a new device type

**Step 1** — Find the exact model string the device reports.

Option A — OpenWISP admin: Device detail → System tab → **Model** field

Option B — SSH into the device:
```bash
cat /tmp/sysinfo/model
```

**Step 2** — Add a new entry to `hardware_ids.json`:

```json
{
    "image_file": "firmware-filename.bin",
    "label": "Nokia CDM Black Box Rev 3.0",
    "boards": ["Exact model string from device"]
}
```

If multiple hardware revisions share the same firmware image, list all boards:

```json
{
    "image_file": "cdm-blackbox-unified.bin",
    "label": "Nokia CDM Black Box (all revisions)",
    "boards": [
        "CDM Black Box Rev 2.0",
        "CDM Black Box rev 1.0"
    ]
}
```

**Step 4** — Restart OpenWISP:

```bash
docker compose restart controller celery-worker
```
---

## Logs and Monitoring

Application logs are written to `./logs/` on the host (mounted into the container):

```bash
# Follow all service logs
docker compose logs -f

# Follow a specific service
docker compose logs -f controller
docker compose logs -f celery-worker
```

Nginx logs are available at `./logs/nginx/access.log` and `./logs/nginx/error.log`.

InfluxDB is accessible on port `8086` for direct metric queries.

---

## Useful Commands

```bash
# Check running services
docker compose ps

# Restart a specific service
docker compose restart controller

# Open a shell in the Django container
docker compose exec controller bash

# Run a Django management command
docker compose exec controller python manage.py <command>

# Run database migrations manually
docker compose exec controller python manage.py migrate

# Collect static files
docker compose exec controller python manage.py collectstatic --noinput

# Stop all services and remove volumes
docker compose down -v --remove-orphans
```

---

## References

- [OpenWISP Documentation](https://openwisp.io/docs/stable/)
- [Django Documentation](https://docs.djangoproject.com/)
- [Celery Documentation](https://docs.celeryq.dev/)
- [Docker Documentation](https://docs.docker.com/)