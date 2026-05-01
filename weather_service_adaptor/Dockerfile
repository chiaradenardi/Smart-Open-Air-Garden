FROM python:3.9-slim
WORKDIR /app
RUN pip install --no-cache-dir cherrypy requests
COPY weather_adaptor.py .
EXPOSE 8085
CMD ["python", "weather_adaptor.py"]