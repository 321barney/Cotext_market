# build: 2026-05-30.2
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app/ ./app/
COPY backend/migrations/ ./migrations/
COPY backend/migrate.py .
COPY backend/entrypoint.sh .
COPY skill.md .
RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]
