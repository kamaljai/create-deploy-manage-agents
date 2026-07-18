FROM python:3.12.10-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml ./
COPY src ./src
RUN python -m pip wheel --wheel-dir /wheels .

FROM python:3.12.10-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    SKILL_ROOT=/app/skill_source

RUN groupadd --gid 10001 agent \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin agent

WORKDIR /app
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/*.whl \
    && rm -rf /wheels
COPY --chown=10001:10001 skill_source ./skill_source
COPY --chown=10001:10001 skill-provenance.json ./skill-provenance.json

USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)"]

CMD ["uvicorn", "skill_agent.api:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]

