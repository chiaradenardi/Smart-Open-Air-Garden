FROM python:3.9-slim
WORKDIR /app
RUN pip install --no-cache-dir paho-mqtt==1.6.1
COPY fault_detection.py .
COPY ../shared_utils/MyMQTT.py .
CMD ["python", "fault_detection.py"]
