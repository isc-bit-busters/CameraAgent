FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    bluez \
    bluetooth \
    dbus \
    libglib2.0-0 \
    libbluetooth-dev \
    && rm -rf /var/lib/apt/lists/*

COPY bridge.py .

RUN pip install --no-cache-dir bleak paho-mqtt

CMD ["python", "bridge.py"]
