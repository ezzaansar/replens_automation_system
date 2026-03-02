# Amazon Replens Automation System - Deployment Guide

This guide provides instructions for deploying the Amazon Replens Automation System using Docker and Docker Compose.

## 1. Prerequisites

- Docker Engine (v20.10+)
- Docker Compose (v2.0+)
- A configured `.env` file (see `getting-started` section in `IMPLEMENTATION_GUIDE.md`)

## 2. Dockerized Deployment

### 2.1. Building the Docker Image

```bash
docker build -t replens-automation .
```

### 2.2. Running with Docker Compose

```bash
docker-compose up -d
```

This will start the following services:

- `web`: The Streamlit dashboard, accessible at `http://localhost:8501`
- `scheduler`: The APScheduler service that runs the automation jobs
- `db`: The PostgreSQL database
- `redis`: The Redis message broker for Celery (if using async tasks)

### 2.3. Verifying the Deployment

```bash
# Check running containers
docker-compose ps

# View logs for a service
docker-compose logs -f web
```

## 3. Production Deployment

For a production environment, it is recommended to use a more robust setup:

- **Web Server:** Gunicorn or Uvicorn behind an Nginx reverse proxy
- **Database:** A managed PostgreSQL service (e.g., Amazon RDS, Google Cloud SQL)
- **Cache:** A managed Redis service (e.g., Amazon ElastiCache, Google Cloud Memorystore)
- **Container Orchestration:** Kubernetes or Docker Swarm for managing containers at scale
- **CI/CD:** A CI/CD pipeline (e.g., Jenkins, GitLab CI, GitHub Actions) for automated testing and deployment
