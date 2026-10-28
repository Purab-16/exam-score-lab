# API image. Build from the project root:
#   docker build -f api/Dockerfile -t exam-score-api .
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # numba (used by shap) needs a writable cache directory for the non-root user
    NUMBA_CACHE_DIR=/tmp/numba

WORKDIR /app

COPY requirements-api.txt .
RUN pip install -r requirements-api.txt

# Only the runtime modules. ml/train.py is left out on purpose: it needs training libraries.
COPY ml/__init__.py ml/paths.py ml/pipeline.py ml/insights.py ./ml/
COPY models ./models
COPY data ./data
COPY api ./api

RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\", \"8000\")}/health')"

# PORT is set by hosts such as Railway or Render; 8000 locally
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
