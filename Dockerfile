FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MOCK_LLM=true \
    CREWAI_DISABLE_TELEMETRY=true \
    CREWAI_TRACING_ENABLED=false \
    OTEL_SDK_DISABLED=true \
    ANONYMIZED_TELEMETRY=false \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    PORT=8000

WORKDIR /app

COPY requirements-api.lock requirements-api.txt requirements-crew.txt requirements-rag.txt ./
RUN python -m pip install --no-cache-dir --disable-pip-version-check \
        torch==2.14.1+cpu --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install --no-cache-dir --disable-pip-version-check -r requirements-api.lock

COPY . .

# Network access is used only while building the image. The final runtime reads
# the pinned model and indexes locally and keeps all generated state ephemeral.
RUN HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 python -m scripts.download_embedding_model \
    && python -m scripts.rebuild_indexes --report /tmp/index-build.json \
    && rm -rf /app/.cache

EXPOSE 8000

CMD ["sh", "-c", "python -m uvicorn api.app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --loop asyncio --no-access-log"]
