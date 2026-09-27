# Build context is apps/api (Render: Root Directory = apps/api).
# apps/api is self-contained, including the committed data/processed snapshot.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/docker-entrypoint.sh \
    && useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE $PORT

CMD ["/app/docker-entrypoint.sh"]
