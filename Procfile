web: python manage.py collectstatic --noinput && python manage.py migrate --noinput && python manage.py create_superuser_if_none && daphne -b 0.0.0.0 -p ${PORT:-8000} tars_site.asgi:application
