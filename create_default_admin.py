import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'barangay_connect.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'barangay.connect2026@gmail.com', '123')
    print("Default admin created successfully.")
else:
    print("Admin already exists.")
