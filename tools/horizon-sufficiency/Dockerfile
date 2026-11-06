FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models/hf \
    HF_HUB_DISABLE_TELEMETRY=1

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd -r horizon && useradd -r -g horizon -m horizon \
    && mkdir -p /models/hf && chown -R horizon:horizon /models /app
COPY --chown=horizon:horizon service.py /app/service.py
USER horizon

EXPOSE 8082
HEALTHCHECK --interval=30s --timeout=5s --start-period=300s --start-interval=3s --retries=3 \
  CMD python -c "import json,os,urllib.request as u; d=json.load(u.build_opener(u.ProxyHandler({})).open('http://127.0.0.1:8082/readyz',timeout=3)); assert d.get('ready') is True and d.get('contract')=='horizon-nli-v1' and d.get('model_id')==os.getenv('MODEL_ID','Horizon-Labs/multilingual-zeroshot-small') and d.get('provider')=='CPUExecutionProvider'" || exit 1
CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8082", "--workers", "1"]
