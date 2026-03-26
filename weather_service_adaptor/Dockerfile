FROM python:3.9-slim

WORKDIR /app

# Installiamo le librerie per il server e per le chiamate API
RUN pip install --no-cache-dir cherrypy requests

# Copiamo lo script dell'adaptor
COPY weather_adaptor.py .

# Espone la porta dell'adaptore
EXPOSE 8085

CMD ["python", "weather_adaptor.py"]