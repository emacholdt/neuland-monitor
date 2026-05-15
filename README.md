# 🚀 Neuland Monitor

A lightweight, high-performance internet connectivity and speed monitoring service. It logs data to **InfluxDB 2.x** and provides a premium, glassmorphism-style dashboard with real-time status and historical analytics.

## ✨ Features

- **Real-time Monitoring**: Pings a target (default: 8.8.8.8) at your preferred frequency.
- **Automated Speedtests**: Runs the official Ookla Speedtest CLI on a schedule (default: 10x daily).
- **Interactive Analytics**:
  - **Ping History**: Real-time line chart for latency trends.
  - **Speed History**: Historical trend for download/upload performance.
  - **Uptime Stats**: Aggregated availability for the last 24h, 7d, 30d, and 90d.
- **Bilingual Support**: Instant toggle between **English** and **German** (including localized date formats).
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

## 📦 Persistence
The application stores its configuration in `/app/data/config.json`. Ensure the `./data` volume is mapped in your `docker-compose.yml` to keep your settings after container updates.

## 🛠️ Tech Stack
- **Backend**: FastAPI (Python 3.11)
- **Database**: InfluxDB 2.x
- **Frontend**: Vanilla JS, CSS (Glassmorphism), Chart.js
- **Tooling**: Ookla Speedtest CLI

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
