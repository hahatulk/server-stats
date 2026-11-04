FROM python:3.13-alpine AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /build

# psutil may need compilation against musl on Alpine.
# Keep the toolchain and kernel headers out of the runtime image.
RUN apk add --no-cache build-base linux-headers
COPY requirements.txt requirements-docker.txt ./
RUN pip install --no-cache-dir --ignore-installed --prefix=/install -r requirements-docker.txt

FROM python:3.13-alpine AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY --from=builder /install/ /usr/local/
COPY server_stats.py gunicorn.conf.py ./
USER 65534:65534
EXPOSE 5000
CMD ["gunicorn", "--config", "/app/gunicorn.conf.py", "server_stats:app"]
