FROM python:3.9-slim

WORKDIR /app

# Installiamo le librerie per MQTT e REST
RUN pip install --no-cache-dir paho-mqtt==1.6.1 requests

# Copiamo il cervello e la classe MyMQTT
COPY smart_irrigation.py .
COPY MyMQTT.py .

# Questo servizio non espone porte (lavora "in uscita" o via MQTT)
CMD ["python", "smart_irrigation.py"]