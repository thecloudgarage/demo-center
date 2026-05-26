FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements-producer.txt .
RUN pip install --no-cache-dir -r requirements-producer.txt

COPY producer.py .

CMD ["python", "producer.py"]
