# PulseOps

PulseOps is a real-time monitoring dashboard for Linux servers and Docker containers. It tracks CPU, RAM and disk usage, detects container crashes, monitors HTTP traffic, stores alert history, and sends email notifications when a threshold is crossed. It runs as a self-hosted tool and does not depend on any third-party monitoring service.

- **Repository:** https://github.com/SyedaAyeshaRashidi/PulseOps
- **Live Dashboard:** http://13.60.249.241:5000
- **Status:** Monitored 24/7 via UptimeRobot

---

## Dashboard Preview

![PulseOps Dashboard Preview](dashboard-preview.png)

---

## Features

### Server Monitoring
- Live CPU, RAM and disk usage with color-coded bars (green, yellow, red)
- Updates every 10 seconds over WebSockets (Socket.IO), with a REST call for the first load
- Dark UI that works on both desktop and mobile

### Docker Container Management
- Lists all running and exited containers using the Docker SDK
- Start, stop and remove containers from the dashboard
- **Volume safety check:** if a container has volumes or bind mounts attached, you get a warning before removing it so you don't lose data by accident
- Launch a new container just by typing an image name
- **409 conflict handling:** if a container with the same name already exists (exited), it gets restarted instead of throwing an error

### Alerting
- **System alerts:** CPU ≥ 85%, RAM ≥ 80%, Disk ≥ 90%, and the value has to stay high for 3 checks in a row, so a single spike doesn't trigger a false alarm
- **Container alerts:** CPU spikes, memory warning (80%), memory critical (90%) and unexpected crashes
- Tells the difference between a container you stopped from the UI and one that actually crashed. Only real crashes send an alert
- Emails go out over SMTP using a Gmail App Password

### Traffic Monitoring
- Reads container access logs and counts HTTP requests from the last 5 minutes
- Request count per container shows up in the table and in the traffic widget

### History
- SQLite stores past alerts and critical metric spikes, so nothing is lost when the app restarts
- Separate Alert History page
- Chart.js graph for critical CPU spikes. It only plots the spikes, not the idle baseline

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask, Flask-SocketIO, Flask-SQLAlchemy |
| Container API | Docker SDK for Python |
| Host metrics | psutil |
| Database | SQLite |
| Real-time | Socket.IO (WebSockets) |
| Frontend | HTML, vanilla JS, CSS Grid / Flexbox, Chart.js |
| Email alerts | Python `smtplib` (SMTP over TLS) |
| Hosting | AWS EC2, systemd, Docker |
| Uptime check | UptimeRobot |

---

## Project Structure

```text
PulseOps/
├── app.py                  # Flask app, routes, alert logic, background thread
├── collector.py            # Host CPU/RAM/Disk metrics via psutil
├── docker_health.py        # Container stats via Docker SDK
├── traffic_monitor.py      # HTTP request count from container logs
├── alerts.py               # Email alerts (SMTP)
├── database.py             # SQLAlchemy models (MetricHistory, AlertHistory)
├── main.py                 # Terminal dashboard (standalone mode)
├── templates/
│   ├── dashboard.html      # Main dashboard (dark UI, Socket.IO, Chart.js)
│   └── alerts.html         # Alert history page
├── docs/
│   └── dashboard-preview.png
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Getting Started

### Prerequisites
- Docker and Docker Compose
- Python 3.10+
- A Gmail account with an App Password (for email alerts)

### Run with Docker Compose

```bash
git clone https://github.com/SyedaAyeshaRashidi/PulseOps.git
cd PulseOps

export GMAIL_ADDRESS="your@gmail.com"
export GMAIL_APP_PASSWORD="your_app_password"

docker compose up -d
```

Then open http://localhost:5000 in your browser.

### Run Locally (without Docker)

```bash
git clone https://github.com/SyedaAyeshaRashidi/PulseOps.git
cd PulseOps

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export GMAIL_ADDRESS="your@gmail.com"
export GMAIL_APP_PASSWORD="your_app_password"

python3 app.py
```

---

## Alert Conditions

| Condition | Threshold | What happens |
|---|---|---|
| System CPU | ≥ 85% for 30s | Email alert |
| System RAM | ≥ 80% for 30s | Email alert |
| System Disk | ≥ 90% for 30s | Email alert |
| Container CPU | ≥ 85% | Email alert right away |
| Container memory (warning) | ≥ 80% | Email alert |
| Container memory (critical) | ≥ 90% | Urgent email alert |
| Container crash | Unexpected exit | Email alert right away |
| Manual stop | Stopped from the UI | No alert |

---

## Deployment

I run PulseOps on an AWS EC2 instance (Ubuntu 24.04) and manage it with systemd, so it keeps running in the background and comes back up after a reboot or a crash.

A minimal unit file looks like this:

```ini
# /etc/systemd/system/pulseops.service
[Unit]
Description=PulseOps Dashboard
After=network.target docker.service
Requires=docker.service

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/PulseOps
EnvironmentFile=/etc/pulseops.env
ExecStart=/home/ubuntu/PulseOps/venv/bin/python app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

The Gmail credentials live in `/etc/pulseops.env` (not in the repo):

```text
GMAIL_ADDRESS=your@gmail.com
GMAIL_APP_PASSWORD=your_app_password
```

Then enable the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pulseops
```

The user running the service needs access to the Docker socket, otherwise the container stats won't load.

---

## Why I Built This

Tools like Grafana, Datadog and Prometheus are great, but they take a lot of setup and usually need extra agents. I wanted to understand how it all works underneath: collecting server metrics, talking to Docker, streaming data to the browser in real time, and sending alerts. So I built it from scratch.
