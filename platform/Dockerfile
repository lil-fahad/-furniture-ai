FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install --require-hashes -r requirements.lock
COPY pyproject.toml models.lock.json alembic.ini ./
COPY src ./src
COPY migrations ./migrations
RUN pip install --no-deps . && useradd --uid 10001 --create-home furniture && mkdir -p /data/objects && chown -R furniture:furniture /data
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "furniture_ai.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--limit-concurrency", "64", "--timeout-keep-alive", "5"]
