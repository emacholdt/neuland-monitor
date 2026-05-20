FROM python:3.11-slim

# Install dependencies for speedtest and ping
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    iputils-ping \
    && curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | bash \
    && apt-get install -y speedtest \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Version injected at build time by CI from git tag, defaults to dev
ARG VERSION=dev
ENV APP_VERSION=${VERSION}

# Copy application code
COPY . .

# Create a volume for data if needed (currently settings are ENV based)
# VOLUME ["/app/data"]

EXPOSE 8181

# Accept license on first run is handled in main.py via flags
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8181"]
