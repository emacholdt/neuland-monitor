import os
import asyncio
import subprocess
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from influxdb_client import InfluxDBClient, Point, WriteOptions
from influxdb_client.client.write_api import SYNCHRONOUS
from pydantic_settings import BaseSettings

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    influxdb_url: str = "http://localhost:8086"
    influxdb_token: str = "your-token"
    influxdb_org: str = "your-org"
    influxdb_bucket: str = "internet_monitor"
    
    ping_target: str = "8.8.8.8"
    ping_interval: int = 60  # seconds
    speedtest_interval: int = 144  # minutes (10 times per day)
    
    admin_password: str = "admin123"
    port: int = 8181

    class Config:
        env_file = ".env"

settings = Settings()

app = FastAPI(title="Internet Monitor")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Shared state for the dashboard
state = {
    "is_online": True,
    "last_ping": None,
    "last_speedtest": None,
    "current_latency": 0.0,
    "download_mbps": 0.0,
    "upload_mbps": 0.0,
}

# InfluxDB Client
influx_client = InfluxDBClient(
    url=settings.influxdb_url,
    token=settings.influxdb_token,
    org=settings.influxdb_org
)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)

def run_ping():
    try:
        # -c 1: send 1 packet, -W 2: wait 2 seconds
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "2", settings.ping_target],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        is_online = result.returncode == 0
        latency = 0.0
        if is_online:
            # Extract latency from ping output (e.g., "time=12.3 ms")
            for line in result.stdout.split('\n'):
                if "time=" in line:
                    latency = float(line.split("time=")[1].split(" ")[0])
                    break
        return is_online, latency
    except Exception as e:
        logger.error(f"Ping failed: {e}")
        return False, 0.0

def run_speedtest():
    try:
        logger.info("Starting Speedtest...")
        # Running official speedtest CLI with JSON output
        result = subprocess.run(
            ["speedtest", "--accept-license", "--accept-gdpr", "-f", "json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            # Conversion from bytes/s to Mbps
            download = data["download"]["bandwidth"] * 8 / 1_000_000
            upload = data["upload"]["bandwidth"] * 8 / 1_000_000
            latency = data["ping"]["latency"]
            return {
                "download": round(download, 2),
                "upload": round(upload, 2),
                "latency": latency,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            logger.error(f"Speedtest failed: {result.stderr}")
            return None
    except Exception as e:
        logger.error(f"Speedtest execution error: {e}")
        return None

async def connectivity_loop():
    while True:
        is_online, latency = run_ping()
        state["is_online"] = is_online
        state["last_ping"] = datetime.utcnow().isoformat()
        state["current_latency"] = latency
        
        # Write to InfluxDB
        try:
            point = Point("connectivity") \
                .tag("target", settings.ping_target) \
                .field("online", 1 if is_online else 0) \
                .field("latency", latency)
            write_api.write(bucket=settings.influxdb_bucket, record=point)
        except Exception as e:
            logger.error(f"Failed to write ping to InfluxDB: {e}")
            
        await asyncio.sleep(settings.ping_interval)

async def speedtest_loop():
    # Initial wait to let connectivity settle
    await asyncio.sleep(10)
    while True:
        # Only run speedtest if we are online
        if state["is_online"]:
            res = run_speedtest()
            if res:
                state["last_speedtest"] = res
                state["download_mbps"] = res["download"]
                state["upload_mbps"] = res["upload"]
                
                # Write to InfluxDB
                try:
                    point = Point("internet_speed") \
                        .field("download", res["download"]) \
                        .field("upload", res["upload"]) \
                        .field("latency", res["latency"])
                    write_api.write(bucket=settings.influxdb_bucket, record=point)
                    logger.info(f"Speedtest result saved: {res['download']} Mbps down / {res['upload']} Mbps up")
                except Exception as e:
                    logger.error(f"Failed to write speedtest to InfluxDB: {e}")
        
        # Sleep for the configured interval (converted to seconds)
        await asyncio.sleep(settings.speedtest_interval * 60)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(connectivity_loop())
    asyncio.create_task(speedtest_loop())

@app.get("/")
async def read_index():
    with open("static/index.html") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.get("/api/status")
async def get_status():
    return state

@app.get("/api/config")
async def get_config(password: Optional[str] = None):
    if password != settings.admin_password:
        raise HTTPException(status_code=403, detail="Forbidden")
    return {
        "ping_interval": settings.ping_interval,
        "speedtest_interval": settings.speedtest_interval,
        "influxdb_url": settings.influxdb_url,
        "influxdb_bucket": settings.influxdb_bucket,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
