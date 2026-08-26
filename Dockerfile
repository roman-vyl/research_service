FROM python:3.12-slim AS builder

WORKDIR /build

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels .


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RESEARCH_HOST=0.0.0.0 \
    RESEARCH_PORT=8080 \
    RESEARCH_ARTIFACTS_ROOT=/data/runs \
    RESEARCH_CONFIGS_ROOT=/data/configs

WORKDIR /app

COPY --from=builder /wheels /wheels

RUN groupadd --gid 10001 research \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent \
        --shell /usr/sbin/nologin research \
    && python -m pip install --no-cache-dir /wheels/*.whl \
    && rm -rf /wheels \
    && mkdir -p /data/runs /data/configs \
    && chown -R 10001:10001 /data \
    && chmod -R 0750 /data \
    && chmod -R a-w /app

VOLUME ["/data"]
EXPOSE 8080

USER 10001:10001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"]

ENTRYPOINT ["research-service"]
