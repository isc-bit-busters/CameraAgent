FROM python:3.12.9

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libglib2.0-0 \
    libgl1-mesa-glx \
    bluez \
    dbus \
    bluetooth \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bridge.py .

CMD ["python", "bridge.py"]
