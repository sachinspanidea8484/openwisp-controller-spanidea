#!/bin/bash
set -e

echo ">>> Restoring default media files into PVC..."
cp -Rn /opt/openwisp/media_defaults/* /opt/openwisp/media/ 2>/dev/null || true

create_superuser() {
    local username="$1"
    local email="$2"
    local password="$3"
    python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username="${username}").exists():
    u = User.objects.create_superuser("${username}", "${email}", "${password}")
    u.is_superuser = True
    u.is_staff = True
    u.save()
    print('Superuser "${username}" created successfully.')
else:
    u = User.objects.get(username="${username}")
    u.is_superuser = True
    u.is_staff = True
    u.save()
    print('User "${username}" already exists — ensured is_superuser=True.')
EOF
}

echo ">>> Running makemigrations..."
python manage.py makemigrations

echo ">>> Running migrate..."
python manage.py migrate --no-input

echo ">>> Creating superuser..."
create_superuser admin admin@example.com admin

TEST_MANAGEMENT_LOAD=True
if [ "$TEST_MANAGEMENT_LOAD" = "true" ] || [ "$TEST_MANAGEMENT_LOAD" = "True" ]; then
    echo "Loading system test cases from XLSX..."
    python manage.py load_system_test_cases --admin-username admin
    echo "System test case loading complete."
else
    echo "TEST_MANAGEMENT_LOAD is not set — skipping system test case load."
fi

echo ">>> Starting Django server..."
python manage.py runserver 0.0.0.0:8000