# API image. Build from the project root:
#   docker build -f api/Dockerfile -t exam-score-api .
FROM python:3.14-slim

# API_ENV=production hides /docs, /redoc and /openapi.json. Override with -e API_ENV=development.
# The other API settings and their defaults are listed in api/settings.py.
ENV API_ENV=production \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements-api.txt .
# Keep the image small: no compiled .pyc files, no test folders of the libraries, and pip itself is
# removed at the end (it is only needed to install, and its bundled libraries were flagged by scanners).
RUN pip install --no-compile -r requirements-api.txt \
 && find /usr/local/lib/python3.14/site-packages -type d \( -name tests -o -name test \) -prune -exec rm -rf {} + \
 && find /usr/local/lib/python3.14/site-packages -type d -name __pycache__ -prune -exec rm -rf {} + \
 && pip uninstall -y pip

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
# --no-server-header: do not announce the server software in every response
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-server-header"]
