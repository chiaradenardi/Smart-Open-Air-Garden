FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY statistics_service.py .

EXPOSE 8082

CMD ["python", "statistics_service.py"]