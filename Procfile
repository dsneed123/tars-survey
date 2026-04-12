web: python manage.py collectstatic --noinput && python manage.py migrate --noinput && python manage.py create_superuser_if_none && gunicorn tars_site.wsgi --log-file -
