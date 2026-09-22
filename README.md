# PulseOps — Container & Infrastructure Monitoring Hub

A real-time DevOps monitoring dashboard built to observe Linux server health and Docker container lifecycle from a single, unified interface. PulseOps continuously tracks system resource utilization, detects container crashes, monitors incoming traffic, persists historical alert data, and fires automated email notifications — all without any third-party monitoring service.

---

## Features

**Real-Time Server Monitoring**
- Live CPU, RAM, and Disk utilization with dynamic color-coded gauges (green → yellow → red)
- 10-second polling via WebSockets (Socket.IO) with instant REST-based initial load

**Docker Container Management**
- Auto-discovers all running and exited containers via Docker SDK
- Start, Stop, and Remove containers directly from the dashboard
- Volume Safety Check — detects attached volumes/bind mounts before removal and shows a warning popup to prevent accidental data loss
- Launch new containers by image name from the UI
- 409 Conflict Protection — if a container with the same name already exists (exited), it is restarted instead of erroring out

**Intelligent Alerting Engine**
- System-level alerts: CPU ≥ 85%, RAM ≥ 80%, Disk ≥ 90% (sustained over 3 consecutive checks to avoid false positives)
- Container-level alerts: per-container CPU spike, memory warning (80%), memory critical (90%), and unexpected crash detection
- Smart crash detection — differentiates between a manual UI stop and an actual crash; alert only fires on genuine crashes
- Email notifications via SMTP (Gmail App Password)

**Traffic Monitoring**
- Parses live container access logs to count HTTP requests in the last 5 minutes
- Per-container request count displayed in the dashboard table and traffic widget

**Persistent History**
- SQLite database stores all past alerts and critical metric spikes
- Alert History page accessible via dashboard (persists across app restarts)
- Critical CPU spike graph powered by Chart.js — only plots anomalies, not idle baseline data

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask, Flask-SocketIO, Flask-SQLAlchemy |
| Container API | Docker SDK for Python (`docker.sock`) |
| Host Telemetry | `psutil` |
| Database | SQLite |
| Real-time | WebSockets via Socket.IO |
| Frontend | HTML5, Vanilla JS, CSS Grid, Chart.js |
| Alerting | Python `smtplib` (SMTP over TLS) |
| Deployment | Docker, Docker Compose |

---

## Project Structure
```
pulseops/
├── app.py                  # Flask app, routes, alert logic, background thread
├── collector.py            # Host CPU/RAM/Disk metrics via psutil
├── docker_health.py        # Docker container stats via Docker SDK
├── traffic_monitor.py      # HTTP request count from container logs
├── alerts.py               # Email alert engine (SMTP)
├── database.py             # SQLAlchemy models (MetricHistory, AlertHistory)
├── main.py                 # CLI terminal dashboard (standalone mode)
├── templates/
│   └── dashboard.html      # Frontend — dark UI, Socket.IO, Chart.js
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Getting Started

### Prerequisites
- Docker and Docker Compose installed
- Gmail account with App Password enabled (for email alerts)

### Run with Docker Compose

```bash
git clone https://github.com/SyedaAyeshaRashidi/pulseops.git
cd pulseops

export GMAIL_ADDRESS="your@gmail.com"
export GMAIL_APP_PASSWORD="your_app_password"

docker compose up -d
```

Open `http://localhost:5000` in your browser.

### Run Locally (without Docker)

```bash
pip install -r requirements.txt

export GMAIL_ADDRESS="your@gmail.com"
export GMAIL_APP_PASSWORD="your_app_password"

python app.py
```

---

## Alert Conditions

| Condition | Threshold | Behavior |
|---|---|---|
| System CPU | ≥ 85% for 30s | Email alert |
| System RAM | ≥ 80% for 30s | Email alert |
| System Disk | ≥ 90% for 30s | Email alert |
| Container CPU | ≥ 85% | Immediate email alert |
| Container Memory Warning | ≥ 80% | Email alert |
| Container Memory Critical | ≥ 90% | Urgent email alert |
| Container Crash | Unexpected exit | Immediate email alert |
| Manual Stop | UI button | No alert triggered |

---

## Deployment

PulseOps is deployed on AWS EC2 (t2.micro, Ubuntu 24.04) using Docker Compose.
UptimeRobot monitors the dashboard itself for external availability checks.

---

## Why PulseOps

Most monitoring tools (Grafana, Datadog, Prometheus) require extensive configuration, external agents, and infrastructure overhead. PulseOps was built from scratch to understand the core mechanics of server telemetry, container introspection, real-time data streaming, and alerting pipelines — the same fundamentals that underpin production-grade observability systems.

---

