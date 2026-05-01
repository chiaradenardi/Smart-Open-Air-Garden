FROM python:3.9-slim
WORKDIR /app
RUN pip install --no-cache-dir cherrypy
COPY service_catalog.py .
COPY catalogManager.json .
EXPOSE 8080
CMD ["python", "service_catalog.py"]