# 🚀 Neuland Monitor

A lightweight, beautiful internet connectivity and speed monitoring service for Linux servers. It logs data to **InfluxDB 2.x** and provides a premium, glassmorphism-style dashboard for real-time status updates.

![Neuland Monitor Dashboard](https://raw.githubusercontent.com/your-username/neuland-monitor/main/static/screenshot.png) *(Add a screenshot here!)*

## ✨ Features

- **Real-time Connectivity**: Pings a target (default: 8.8.8.8) every minute.
- **Speedtests**: Runs the official Ookla Speedtest CLI 10 times a day.
- **Time-Series Logging**: Saves all metrics (ping, download, upload) to InfluxDB.
- **SO-Friendly Dashboard**: A simple, beautiful web UI on port 8181 designed for family use.
- **Admin Panel**: Password-protected section to view current configuration.
- **Dockerized**: Deploy in seconds using Docker Compose.

## 🛠️ Quick Start

### 1. Clone & Configure
```bash
git clone https://github.com/your-username/neuland-monitor.git
cd neuland-monitor
cp .env.example .env
```

### 2. Set your Environment Variables
Edit the `.env` file with your InfluxDB details:
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

## 📦 Tech Stack

- **Backend**: FastAPI (Python 3.11)
- **Database**: InfluxDB 2.x
- **Frontend**: Vanilla JS, CSS (Glassmorphism)
- **Monitoring**: Ookla Speedtest CLI

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
