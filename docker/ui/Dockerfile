FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/main.py .
COPY frontend/ ./static/

EXPOSE 8080

CMD ["python", "main.py"]
