FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_DEBUG=0 \
    DJANGO_SETTINGS_MODULE=config.aws_settings

WORKDIR /app
RUN useradd --uid 10001 --create-home bytebistro \
    && install -d -o bytebistro -g bytebistro /app/collected-static

COPY requirements.txt requirements-aws.txt ./
RUN pip install --no-cache-dir -r requirements-aws.txt
ADD --chmod=0444 https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem /app/rds-ca.pem
COPY config/ ./config/
COPY shop/ ./shop/
COPY static/ ./static/
COPY templates/ ./templates/
COPY manage.py ./

USER bytebistro
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "config.wsgi:application"]
