FROM python:3.11.11-slim-bookworm@sha256:081075da77b2b55c23c088251026fb69a7b2bf92471e491ff5fd75c192fd38e5
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_XET=1
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock && pip check \
    && groupadd -r reranker && useradd -r -g reranker -m reranker \
    && mkdir -p /models/hf && chown -R reranker:reranker /models /app
COPY --chown=reranker:reranker client.py service.py ./
USER reranker
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=1800s --start-interval=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:8080/readyz', timeout=3)" || exit 1
CMD ["python", "service.py"]
