# Generated by Django 3.0.7 on 2020-07-05 17:50

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("openwisp_radius", "0012_populate_uuid_field"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="nas",
            name="id",
        ),
        migrations.RemoveField(
            model_name="radiusaccounting",
            name="id",
        ),
        migrations.RemoveField(
            model_name="radiuscheck",
            name="id",
        ),
        migrations.RemoveField(
            model_name="radiusgroupcheck",
            name="id",
        ),
        migrations.RemoveField(
            model_name="radiusgroupreply",
            name="id",
        ),
        migrations.RemoveField(
            model_name="radiuspostauth",
            name="id",
        ),
        migrations.RemoveField(
            model_name="radiusreply",
            name="id",
        ),
        migrations.RemoveField(
            model_name="radiususergroup",
            name="id",
        ),
        migrations.AlterField(
            model_name="nas",
            name="uuid",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, primary_key=True, serialize=False
            ),
        ),
        migrations.AlterField(
            model_name="radiuscheck",
            name="uuid",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, primary_key=True, serialize=False
            ),
        ),
        migrations.AlterField(
            model_name="radiusgroupcheck",
            name="uuid",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, primary_key=True, serialize=False
            ),
        ),
        migrations.AlterField(
            model_name="radiusgroupreply",
            name="uuid",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, primary_key=True, serialize=False
            ),
        ),
        migrations.AlterField(
            model_name="radiuspostauth",
            name="uuid",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, primary_key=True, serialize=False
            ),
        ),
        migrations.AlterField(
            model_name="radiusreply",
            name="uuid",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, primary_key=True, serialize=False
            ),
        ),
        migrations.AlterField(
            model_name="radiususergroup",
            name="uuid",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, primary_key=True, serialize=False
            ),
        ),
        migrations.AlterField(
            model_name="radiusaccounting",
            name="unique_id",
            field=models.CharField(
                db_column="acctuniqueid",
                max_length=32,
                primary_key=True,
                serialize=False,
                unique=True,
                verbose_name="accounting unique ID",
            ),
        ),
        migrations.RenameField(
            model_name="nas",
            old_name="uuid",
            new_name="id",
        ),
        migrations.RenameField(
            model_name="radiuscheck",
            old_name="uuid",
            new_name="id",
        ),
        migrations.RenameField(
            model_name="radiusgroupcheck",
            old_name="uuid",
            new_name="id",
        ),
        migrations.RenameField(
            model_name="radiusgroupreply",
            old_name="uuid",
            new_name="id",
        ),
        migrations.RenameField(
            model_name="radiuspostauth",
            old_name="uuid",
            new_name="id",
        ),
        migrations.RenameField(
            model_name="radiusreply",
            old_name="uuid",
            new_name="id",
        ),
        migrations.RenameField(
            model_name="radiususergroup",
            old_name="uuid",
            new_name="id",
        ),
    ]
