# NLP & Vector Processing Worker (Python 3.11 / FastAPI)
# Build context: repository root (needs db/init.sql)
FROM python:3.11-slim

ARG INSTALL_ML=true
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HF_HOME=/models PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app
COPY nlp-worker/requirements.txt nlp-worker/requirements-ml.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Real FinBERT + sentence-transformers + headless Chromium. Set INSTALL_ML=false for a slim image
# that runs the deterministic lite encoders and the XHR interceptor instead.
RUN if [ "$INSTALL_ML" = "true" ]; then \
      pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu && \
      pip install --no-cache-dir -r requirements-ml.txt && \
      python -m playwright install --with-deps chromium ; \
    fi

COPY db ./db
COPY nlp-worker/app ./app
COPY nlp-worker/tests ./tests

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=20 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/healthz')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
