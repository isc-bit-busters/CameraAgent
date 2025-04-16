FROM python:3.11-slim

WORKDIR /app
COPY bridge.py .

RUN pip install bleak paho-mqtt

CMD ["python", "bridge.py"]
