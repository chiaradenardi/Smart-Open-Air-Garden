FROM python:3.9-slim

WORKDIR /app

RUN pip install --no-cache-dir flask requests python-dotenv

COPY statistics_service.py .

EXPOSE 8082

CMD ["python", "statistics_service.py"]