from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import Permission


def create_default_permissions(apps, schema_editor):
    """Create default permissions for all apps"""
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None


def assign_permissions_to_groups(apps, schema_editor):
    """Assign test management permissions to default groups"""
    create_default_permissions(apps, schema_editor)
    
    Group = apps.get_model("openwisp_users", "Group")
    
    try:
        admin = Group.objects.get(name="Administrator")
        operator = Group.objects.get(name="Operator")
    except Group.DoesNotExist:
        # Groups don't exist, skip
        return
    
    # Define permissions
    app_label = "test_management"
    
    # Administrators can manage everything
    admin_permissions = [
        "add_testcategory",
        "change_testcategory",
        "delete_testcategory",
        "view_testcategory",
    ]
    
    # Operators can only view
    operator_permissions = [
        "view_testcategory",
    ]
    
    # Assign permissions to administrators
    for perm_codename in admin_permissions:
        try:
            permission = Permission.objects.get(
                codename=perm_codename,
                content_type__app_label=app_label,
            )
            admin.permissions.add(permission)
        except Permission.DoesNotExist:
            pass
    
    # Assign permissions to operators
    for perm_codename in operator_permissions:
        try:
            permission = Permission.objects.get(
                codename=perm_codename,
                content_type__app_label=app_label,
            )
            operator.permissions.add(permission)
        except Permission.DoesNotExist:
            pass