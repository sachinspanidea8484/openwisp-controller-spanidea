from django.db import migrations

def remove_testsuitecase_permissions(apps, schema_editor):
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    
    try:
        ct = ContentType.objects.get(
            app_label='test_management',
            model='testsuitecase'
        )
        # Delete all permissions for TestSuiteCase
        Permission.objects.filter(content_type=ct).delete()
    except ContentType.DoesNotExist:
        pass

def reverse_func(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('test_management', '0001_initial'),  # Replace with your actual initial migration
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(
            remove_testsuitecase_permissions,
            reverse_func
        ),
    ]