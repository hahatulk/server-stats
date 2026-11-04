FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt requirements-docker.txt ./
RUN pip install --no-cache-dir -r requirements-docker.txt

COPY server_stats.py gunicorn.conf.py ./
USER 65534:65534
EXPOSE 5000
CMD ["gunicorn", "--config", "/app/gunicorn.conf.py", "server_stats:app"]
