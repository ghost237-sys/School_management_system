web: bash -lc "python manage.py collectstatic --noinput && python manage.py migrate --noinput && gunicorn Analitica.wsgi:application --workers=3 --timeout=120 --bind 0.0.0.0:$PORT --log-file -"
