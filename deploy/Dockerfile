# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
WORKDIR /app
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
EXPOSE 8787
ENV AIDB_BIND=127.0.0.1
ENV AIDB_PORT=8787

# Default image = 配置台 + 执行器: PG/MySQL drivers + FastAPI/uvicorn. No dmPython.
FROM base AS default
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[default]"
CMD ["python", "-m", "aidb.web"]

# Optional extras image — NOT the default. Never put dmPython in default.
# FROM default AS dameng
# RUN pip install --no-cache-dir ".[dameng]"
# CMD ["python", "-m", "aidb.web"]
