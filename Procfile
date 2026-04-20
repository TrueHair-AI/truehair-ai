web: gunicorn run:app --timeout 120 --access-logformat '%(m)s %(U)s %(s)s %(b)s %(L)s %({x-request-id}i)s'
release: flask db upgrade && python seed_hairstyles.py && python seed_stylists.py