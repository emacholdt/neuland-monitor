import os
import asyncio
import subprocess
import json
import logging
from datetime import datetime, timezone
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

CONFIG_PATH = "data/config.json"

class Settings(BaseSettings):
    influxdb_url: str = "http://localhost:8086"
    influxdb_token: str = "your-token"
    influxdb_org: str = "your-org"
    influxdb_bucket: str = "neuland_monitor"
    
    ping_target: str = "8.8.8.8"
    ping_interval: int = 60  # seconds
    speedtest_interval: int = 144  # minutes (10 times per day)
    
    admin_password: str = "admin123"
    port: int = 8181

    class Config:
        env_file = ".env"
        extra = "allow"

def load_settings():
    base = Settings()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                overrides = json.load(f)
                for key, value in overrides.items():
                    if hasattr(base, key):
                        setattr(base, key, value)
            logger.info("Loaded settings overrides from config.json")
        except Exception as e:
            logger.error(f"Failed to load config.json: {e}")
    return base

settings = load_settings()

app = FastAPI(title="Neuland Monitor")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Shared state for the dashboard
state = {
    "is_online": True,
    "last_ping": None,
    "last_speedtest": None,
    "current_latency": 0.0,
    "download_mbps": 0.0,
    "upload_mbps": 0.0,
    "is_running_speedtest": False,
    "ping_history": [],  # List of {time, latency, online}
    "speed_history": [], # List of {time, download, upload}
}

# InfluxDB Client Helper
def get_influx_client():
    return InfluxDBClient(
        url=settings.influxdb_url,
        token=settings.influxdb_token,
        org=settings.influxdb_org
    )

influx_client = get_influx_client()
write_api = influx_client.write_api(write_options=SYNCHRONOUS)

async def load_historical_data():
    global influx_client
    try:
        logger.info("Loading historical data from InfluxDB...")
        # Last 60 pings
        ping_query = f'''
            from(bucket: "{settings.influxdb_bucket}")
            |> range(start: -24h)
            |> filter(fn: (r) => r._measurement == "connectivity" and r._field == "latency")
            |> sort(columns: ["_time"], desc: true)
            |> limit(n: 60)
        '''
        online_query = f'''
            from(bucket: "{settings.influxdb_bucket}")
            |> range(start: -24h)
            |> filter(fn: (r) => r._measurement == "connectivity" and r._field == "online")
            |> sort(columns: ["_time"], desc: true)
            |> limit(n: 60)
        '''
        
        # We'll just fetch latency and assume online if latency > 0 or based on online field
        # Actually, let's just fetch online field first as it's more reliable for status
        result = influx_client.query_api().query(query=online_query, org=settings.influxdb_org)
        pings = []
        for table in result:
            for record in table.records:
                pings.append({
                    "time": record.get_time().isoformat(),
                    "online": bool(record.get_value()),
                    "latency": 0.0 # Will fill in next
                })
        
        # Fetch latency to match
        latency_result = influx_client.query_api().query(query=ping_query, org=settings.influxdb_org)
        for table in latency_result:
            for i, record in enumerate(table.records):
                if i < len(pings):
                    pings[i]["latency"] = record.get_value()
        
        if pings:
            state["ping_history"] = sorted(pings, key=lambda x: x["time"])
            state["is_online"] = state["ping_history"][-1]["online"]
            state["last_ping"] = state["ping_history"][-1]["time"]

        # Last 20 speedtests
        speed_query = f'''
            from(bucket: "{settings.influxdb_bucket}")
            |> range(start: -30d)
            |> filter(fn: (r) => r._measurement == "internet_speed")
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
            |> sort(columns: ["_time"], desc: true)
            |> limit(n: 20)
        '''
        speed_result = influx_client.query_api().query(query=speed_query, org=settings.influxdb_org)
        speeds = []
        for table in speed_result:
            for record in table.records:
                speeds.append({
                    "time": record.get_time().isoformat(),
                    "download": record.values.get("download", 0.0),
                    "upload": record.values.get("upload", 0.0),
                    "timestamp": record.get_time().isoformat()
                })
        
        if speeds:
            state["speed_history"] = sorted(speeds, key=lambda x: x["time"])
            last = state["speed_history"][-1]
            state["last_speedtest"] = last
            state["download_mbps"] = last["download"]
            state["upload_mbps"] = last["upload"]
            
        logger.info(f"Historical data loaded: {len(state['ping_history'])} pings, {len(state['speed_history'])} speedtests")
    except Exception as e:
        logger.warning(f"Could not load historical data (this is normal if InfluxDB is not ready): {e}")

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
                "timestamp": datetime.now(timezone.utc).isoformat()
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
        # Update history (keep last 60 pings)
        now = datetime.now(timezone.utc).isoformat()
        state["last_ping"] = now
        state["ping_history"].append({
            "time": now,
            "latency": latency,
            "online": is_online
        })
        if len(state["ping_history"]) > 60:
            state["ping_history"].pop(0)

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
    # Wait longer at startup to avoid congestion
    await asyncio.sleep(60)
    while True:
        # Check if we have a last speedtest time
        now = datetime.now(timezone.utc)
        last_time = None
        if state["last_speedtest"] and "timestamp" in state["last_speedtest"]:
            try:
                last_time = datetime.fromisoformat(state["last_speedtest"]["timestamp"].replace('Z', '+00:00'))
            except Exception:
                pass
        
        should_run = False
        if not last_time:
            should_run = True
        else:
            elapsed_mins = (now - last_time).total_seconds() / 60
            if elapsed_mins >= settings.speedtest_interval:
                should_run = True
            else:
                # Sleep the remaining time
                wait_time = (settings.speedtest_interval - elapsed_mins) * 60
                logger.info(f"Next scheduled speedtest in {round(wait_time/60, 1)} minutes")
                await asyncio.sleep(max(wait_time, 60))
                continue

        # Only run speedtest if we are online and not already running one
        if should_run and state["is_online"] and not state["is_running_speedtest"]:
            await perform_speedtest()
        
        # Standard sleep until next interval
        await asyncio.sleep(settings.speedtest_interval * 60)

async def perform_speedtest():
    state["is_running_speedtest"] = True
    try:
        # Run blocking subprocess in a separate thread
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, run_speedtest)
        
        if res:
            state["last_speedtest"] = res
            state["download_mbps"] = res["download"]
            state["upload_mbps"] = res["upload"]
            
            # Update history (keep last 20 speedtests)
            state["speed_history"].append({
                "time": res["timestamp"],
                "download": res["download"],
                "upload": res["upload"]
            })
            if len(state["speed_history"]) > 20:
                state["speed_history"].pop(0)

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
    finally:
        state["is_running_speedtest"] = False

@app.on_event("startup")
async def startup_event():
    await load_historical_data()
    asyncio.create_task(connectivity_loop())
    asyncio.create_task(speedtest_loop())

@app.get("/")
async def read_index():
    with open("static/index.html") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.get("/api/status")
async def get_status():
    # Include current latency from the last ping
    if state["ping_history"]:
        state["current_latency"] = state["ping_history"][-1]["latency"]
    return state

@app.get("/api/uptime")
async def get_uptime():
    periods = {
        "1h": "-1h",
        "24h": "-24h",
        "7d": "-7d",
        "30d": "-30d",
        "90d": "-90d"
    }
    uptimes = {}
    
    for label, duration in periods.items():
        try:
            query = f'from(bucket: "{settings.influxdb_bucket}") |> range(start: {duration}) |> filter(fn: (r) => r._measurement == "connectivity" and r._field == "online") |> mean()'
            result = influx_client.query_api().query(query=query, org=settings.influxdb_org)
            if result and len(result) > 0 and len(result[0].records) > 0:
                uptimes[label] = round(result[0].records[0].get_value() * 100, 3)
            else:
                # Fallback to memory for 1h if DB is empty/failing
                if label == "1h":
                    pings = [p["online"] for p in state["ping_history"]]
                    if pings:
                        uptimes[label] = round(sum(pings) / len(pings) * 100, 3)
                    else:
                        uptimes[label] = 100.0
                else:
                    uptimes[label] = None
        except Exception as e:
            logger.error(f"Uptime query failed for {label}: {e}")
            uptimes[label] = None
            
    return uptimes

@app.get("/api/events")
async def get_events(page: int = 1, limit: int = 10):
    # This queries for downtime events (online == 0)
    # We look for transitions or just segments of downtime
    # For simplicity, we'll fetch raw 0s and group them if possible, 
    # but Flux is better at this.
    try:
        # Simplified: fetch last X downtime points
        query = f'''
            from(bucket: "{settings.influxdb_bucket}")
            |> range(start: -30d)
            |> filter(fn: (r) => r._measurement == "connectivity" and r._field == "online" and r._value == 0)
            |> sort(columns: ["_time"], desc: true)
            |> limit(n: {limit}, offset: {(page-1)*limit})
        '''
        result = influx_client.query_api().query(query=query, org=settings.influxdb_org)
        events = []
        for table in result:
            for record in table.records:
                events.append({
                    "timestamp": record.get_time().isoformat(),
                    "status": "Offline"
                })
        return events
    except Exception as e:
        logger.error(f"Events query failed: {e}")
        return []

@app.get("/api/config")
async def get_config(request: Request):
    password = request.headers.get("X-Admin-Password")
    if password != settings.admin_password:
        raise HTTPException(status_code=403, detail="Forbidden")
    return {
        "ping_interval": settings.ping_interval,
        "speedtest_interval": settings.speedtest_interval,
        "influxdb_url": settings.influxdb_url,
        "influxdb_token": settings.influxdb_token,
        "influxdb_org": settings.influxdb_org,
        "influxdb_bucket": settings.influxdb_bucket,
        "ping_target": settings.ping_target,
    }

@app.post("/api/config")
async def update_config(request: Request):
    global settings, influx_client, write_api
    
    # Check password in header
    password = request.headers.get("X-Admin-Password")
    if password != settings.admin_password:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    new_data = await request.json()
    
    # Update current settings
    for key, value in new_data.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    
    # Save to file
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            to_save = {k: getattr(settings, k) for k in settings.__dict__ if not k.startswith('_')}
            json.dump(to_save, f, indent=4)
        
        # Re-initialize InfluxDB client
        influx_client = get_influx_client()
        write_api = influx_client.write_api(write_options=SYNCHRONOUS)
        
        logger.info("Configuration updated and saved to config.json")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to save configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/speedtest/trigger")
async def trigger_speedtest(request: Request):
    password = request.headers.get("X-Admin-Password")
    if password != settings.admin_password:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    if state["is_running_speedtest"]:
        return {"status": "already_running"}
    
    if not state["is_online"]:
        return {"status": "offline_cannot_run"}

    # Start speedtest in the background
    asyncio.create_task(perform_speedtest())
    return {"status": "started"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
