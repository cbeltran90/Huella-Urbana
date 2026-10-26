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


USER app
EXPOSE 8000


CMD ["gunicorn", "config.wsgi:application", "-c", "gunicorn.conf.py"]