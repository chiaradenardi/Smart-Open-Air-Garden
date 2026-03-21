FROM python:3.9-slim

WORKDIR /app

# Installiamo solo CherryPy
RUN pip install --no-cache-dir cherrypy

# Copiamo lo script e il database JSON
COPY service_catalog.py .
COPY catalogManager.json .

# Espone la porta del catalogo
EXPOSE 8080

CMD ["python", "service_catalog.py"]