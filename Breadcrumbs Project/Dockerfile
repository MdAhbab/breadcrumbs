# Breadcrumbs, in one container.
#
# Two stages. The first builds the web app with Node and throws Node away; the
# second is a Python image that runs the API and serves that bundle from the
# same port. One process, one URL, no reverse proxy.
#
#   docker build -t breadcrumbs .
#   docker run -p 8000:8000 breadcrumbs
#
# There is deliberately no GPU stage and no separate model server. The detector
# is a 3,796-parameter network of about 18 KB and it runs on the CPU inside the
# API process in roughly a millisecond. See DEPLOY.md for why that is a property
# of the model rather than a compromise.

# --------------------------------------------------------------------------
FROM node:20-slim AS web

WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# Same origin in a single container, so the client calls /api on whatever host
# it was served from rather than a hardcoded localhost.
ENV VITE_API_URL=""
RUN npm run build

# --------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# The CPU build of PyTorch. The default index would pull the CUDA wheels, which
# are about 2 GB of driver payload this image will never use.
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch \
 && pip install -r backend/requirements.txt

# The system, the API, the corpus and the trained weights. The corpus is in the
# repository on purpose: a container that has to generate 20,000 documents on
# first boot is a container that fails its health check.
COPY model/ ./model/
COPY data/ ./data/
COPY backend/ ./backend/
COPY pyproject.toml ./
COPY --from=web /web/dist ./frontend/dist

# A real secret is required when debug is off; the app refuses to start with the
# development default, which is the correct behaviour and not a bug to work
# around here. Set BREADCRUMBS_SECRET_KEY at run time.
ENV BREADCRUMBS_DEBUG=false \
    PORT=8000

EXPOSE 8000

# The ledger is built in memory on every boot, which takes about 40 seconds of
# genuine work. The API answers immediately and reports its progress, so a
# health check should look at /api/health and accept "building" as alive.
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=30 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=4).status==200 else 1)"

WORKDIR /app/backend
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
