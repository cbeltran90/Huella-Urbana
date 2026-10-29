# ---------- Etapa 1: compila el CSS con el binario standalone de Tailwind ----------
FROM debian:bookworm-slim AS css
ARG TARGETARCH
ARG TAILWIND_VERSION=v4.1.11
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
RUN case "$TARGETARCH" in \
      amd64) A=x64 ;; \
      arm64) A=arm64 ;; \
      *) echo "Arquitectura no soportada: $TARGETARCH" && exit 1 ;; \
    esac \
 && curl -fsSL -o /usr/local/bin/tailwindcss \
      "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-${A}" \
 && chmod +x /usr/local/bin/tailwindcss
WORKDIR /build
COPY static/src static/src
COPY templates templates
COPY apps apps
RUN mkdir -p static/css \
 && tailwindcss -i static/src/input.css -o static/css/app.css --minify


# ---------- Etapa 2: imagen de la aplicación ----------
FROM python:3.12-slim-bookworm

ARG REQUIREMENTS=base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Librerías de sistema para GeoDjango (GDAL, GEOS, PROJ)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      gdal-bin libgdal-dev libgeos-dev libproj-dev \
 && rm -rf /var/lib/apt/lists/*

# Usuario sin privilegios (uid 1000 coincide con el usuario típico del host)
RUN groupadd --gid 1000 app \
 && useradd --uid 1000 --gid 1000 --create-home app

WORKDIR /app

COPY requirements/ requirements/
RUN pip install -r requirements/${REQUIREMENTS}.txt

# Carpetas que luego se montan como volúmenes: deben pertenecer a "app"
RUN mkdir -p /app/media /app/staticfiles \
 && chown -R app:app /app

COPY --chown=app:app . .
COPY --from=css --chown=app:app /build/static/css/app.css /app/static/css/app.css

USER app
EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "-c", "gunicorn.conf.py"]
