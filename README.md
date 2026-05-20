<p align="center">
  <img src="https://raw.githubusercontent.com/emacholdt/neuland-monitor/main/static/logo.svg" alt="Neuland Monitor Logo" width="120" />
</p>

<h1 align="center">Neuland Monitor</h1>

<p align="center">
  <a href="https://github.com/emacholdt/neuland-monitor/actions/workflows/docker.yml">
    <img src="https://github.com/emacholdt/neuland-monitor/actions/workflows/docker.yml/badge.svg" alt="Build Status" />
  </a>
  <a href="https://hub.docker.com/r/emacholdt/neuland-monitor">
    <img src="https://img.shields.io/docker/pulls/emacholdt/neuland-monitor.svg" alt="Docker Pulls" />
  </a>
  <a href="https://hub.docker.com/r/emacholdt/neuland-monitor">
    <img src="https://img.shields.io/docker/image-size/emacholdt/neuland-monitor/latest.svg" alt="Docker Image Size" />
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/github/license/emacholdt/neuland-monitor.svg" alt="License" />
  </a>
</p>

<p align="center">
  A lightweight, high-performance internet connectivity and speed monitoring service. It logs data to <strong>InfluxDB 2.x</strong> and provides a premium, glassmorphism-style dashboard with real-time status and historical analytics.
</p>

## ✨ Features

- **Real-time Monitoring**: Pings a target (default: 8.8.8.8) at your preferred frequency.
- **Automated Speedtests**: Runs the official Ookla Speedtest CLI on a schedule (default: 10x daily).
- **Interactive Analytics**:
  - **Ping History**: Real-time line chart for latency trends.
  - **Speed History**: Historical trend for download/upload performance.
  - **Uptime Stats**: Aggregated availability for the last 24h, 7d, 30d, and 90d.
  - **Downtime History**: Grouped list of continuous offline phases (last 30 days) with start, end, duration, and check counts with interactive click-to-sort headers.
- **Multilingual Support**: Instant toggle between **English**, **German**, and **Saxon** dialect (including localized date formats).
- **Persistent Settings**: Edit monitoring intervals and database credentials directly from the UI; settings persist across container restarts.
- **Security Hardened**: Admin API uses secure custom headers for authentication; sensitive data is protected in logs.
- **Smart Startup**: Automatically reloads historical data from InfluxDB upon restart to keep your charts populated.
- **Dockerized**: Deploy in seconds using Docker Compose.

## 🛠️ Installation

### 1. Clone & Configure
```bash
git clone https://github.com/your-username/neuland-monitor.git
cd neuland-monitor
cp .env.example .env
```

### 2. Configure Environment
Edit the `.env` file with your credentials. Note that special characters in the password should be escaped with `$$`.
```ini
INFLUXDB_URL=http://your-influxdb-ip:8086
INFLUXDB_TOKEN=your-token
INFLUXDB_ORG=your-org
INFLUXDB_BUCKET=neuland_monitor
ADMIN_PASSWORD=your-secret-password
```

### 3. Build & Run
```bash
docker-compose up -d --build
```
Access your dashboard at `http://your-server-ip:8181`.

### 💻 Local Development (Alternative)
You can run the service locally with a single command using `uv` (it will automatically resolve, install, and cache the dependencies):
```bash
uv run --with-requirements requirements.txt uvicorn main:app --port 8182
```

## 📦 Persistence
The application stores its configuration in `/app/data/config.json`. Ensure the `./data` volume is mapped in your `docker-compose.yml` to keep your settings after container updates.

## 🛠️ Tech Stack
- **Backend**: FastAPI (Python 3.11)
- **Database**: InfluxDB 2.x
- **Frontend**: Vanilla JS, CSS (Glassmorphism), Chart.js
- **Tooling**: Ookla Speedtest CLI

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
