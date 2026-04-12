FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=tars_site.settings.prod

RUN pip install --upgrade pip

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN SECRET_KEY=collectstatic-placeholder ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "tars_site.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
