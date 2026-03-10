#!/bin/bash

create_superuser () {
    local username="\$1"
    local email="\$2"
    local password="\$3"
    cat <<EOF | python manage.py shell
from django.contrib.auth import get_user_model

User = get_user_model()

if not User.objects.filter(username="$username").exists():
    User.objects.create_superuser("$username", "$email", "$password")
else:
    print('User "{}" exists already, not created'.format("$username"))
EOF
}

python manage.py makemigrations
python manage.py migrate --no-input

create_superuser admin admin@example.com admin

TEST_MANAGEMENT_LOAD=True

if [ "$TEST_MANAGEMENT_LOAD" = "true" ] || [ "$TEST_MANAGEMENT_LOAD" = "True" ]; then
    echo "Loading system test cases from XLSX..."
    python manage.py load_system_test_cases --admin-username admin
    echo "System test case loading complete."
else
    echo "TEST_MANAGEMENT_LOAD is not set — skipping system test case load."
fi

python manage.py runserver 0.0.0.0:8000