#  OpenWISP Controller (Docker Setup)

This project provides a **Dockerized setup** for running the **OpenWISP Controller**, an open-source **network management system** for OpenWrt devices.  

It allows you to:  
-  Manage devices centrally via a web interface  
-  Apply and monitor configurations across multiple routers  
-  Collect & analyze network data (with InfluxDB)  
-  Automate background tasks with Celery  

---

## 📂 Project Structure


├── docker-compose.yml          # Docker Compose configuration
├── Dockerfile                  # Controller Docker image (Django app)
├── requirements.txt             # Python dependencies
├── openwisp-controller/         # Controller source code
│   ├── openwisp-users/          # User management
│   ├── openwisp-ipam/           # IP address management
│   ├── openwisp-notifications/  # Notifications
│   ├── openwisp-utils/          # Common utilities
│   ├── netjsonconfig/           # Network configuration
│   ├── netdiff/                 # Configuration diffs
│   ├── django-x509/             # Certificate management
│   ├── django-loci/             # Location tracking
│   └── tests/                   # Project tests
├── logs/                        # Log files (nginx, app)
├── media/                       # User uploaded files
└── README.md


---

## 🔧 Prerequisites

Make sure these are installed on your system:
meanwhile you install docker  (v28+ recommended) and docker compose on both server.

- [Docker](https://docs.docker.com/get-docker/) (v28+ recommended)  
- [Docker Compose](https://docs.docker.com/compose/install/) (v2.20+ recommended)  
- Git  

Check versions:

docker --version
docker compose version


---

## ⚙️ Setup & Installation

1. **Go to project directory**   
   cd openwisp-controller
2. **Build and start services**
   docker compose up -d --build
   

   This will start:
   - **Django (Controller API + UI)**
   - **PostgreSQL + PostGIS (Database)**
   - **Redis (Cache & broker)**
   - **Celery Worker + Beat** (background tasks & schedules)
   - **InfluxDB** (time-series DB)
   - **Nginx** (reverse proxy)

3. **Access the application**
   - Web UI → [http://127.0.0.1](http://127.0.0.1)  # Use Your Intance IP
   - Admin Panel → [http://127.0.0.1/admin](http://127.0.0.1/admin)   # Use Your Intance IP

4. **Default Login**
   
   Username: admin
   Email: admin@example.com
   Password: admin
   
   ⚠️ Please **change this password** after first login!

6. **Change Test Management Settings**
     EXECUTOR_SERVER_IP    (Use Cloud IP || Domain)
     OPENWISP_SERVER_IP (Use Cloud IP || Domain)


## 📊 Logs & Monitoring
- **App Logs** → `./logs/`  
- **Nginx Logs** → `./logs/nginx/`  
- **Container Logs**:
  
  docker compose logs -f
  

- **Metrics (InfluxDB)** → available at port `8086`  

---

## 🔧 Useful Docker Commands

- Check running containers:  
  
  docker compose ps
  

- Restart a service:  
  
  docker compose restart <service>
  

- Enter Django container (for shell/debugging):  
  
  docker compose exec controller bash
  

- Run Django management command:  
  
  docker compose exec controller python manage.py <command>
  

- Stop & clean up:  
  
  docker compose down -v --remove-orphans
  

## 📚 More Resources

- [OpenWISP Documentation](https://openwisp.org/docs/)  
- [Django Docs](https://docs.djangoproject.com/)  
- [Celery Docs](https://docs.celeryproject.org/)  
- [Docker Docs](https://docs.docker.com/)  

