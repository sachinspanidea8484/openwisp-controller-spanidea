# Generated by Django 3.0.8 on 2020-07-30 18:27

import re
import uuid
from urllib.parse import urljoin

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
import jsonfield.fields
import model_utils.fields
import private_storage.fields
import private_storage.storage.files
import swapper
from django.conf import settings
from django.db import migrations, models

import openwisp_radius.base.models
import openwisp_radius.base.validators
import openwisp_radius.utils
import openwisp_users.mixins
import openwisp_utils.base
import openwisp_utils.utils
from openwisp_radius.settings import CSV_URL_PATH, RADIUS_API_BASEURL


class Migration(migrations.Migration):
    nas_model = swapper.get_model_name("openwisp_radius", "Nas")
    model_app_label = swapper.split(nas_model)[0]
    dependencies = [
        swapper.dependency("openwisp_users", "Organization"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        (model_app_label, "0001_initial_freeradius"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="radiusaccounting",
            name="id",
        ),
        migrations.AddField(
            model_name="nas",
            name="details",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="nas",
            name="organization",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=swapper.get_model_name("openwisp_users", "Organization"),
                verbose_name="organization",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="radiusaccounting",
            name="delegated_ipv6_prefix",
            field=models.CharField(
                blank=True,
                db_column="delegatedipv6prefix",
                max_length=44,
                null=True,
                validators=[openwisp_radius.base.validators.ipv6_network_validator],
                verbose_name="delegated IPv6 prefix",
            ),
        ),
        migrations.AddField(
            model_name="radiusaccounting",
            name="details",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="radiusaccounting",
            name="framed_interface_id",
            field=models.CharField(
                blank=True,
                db_column="framedinterfaceid",
                max_length=19,
                null=True,
                verbose_name="framed interface ID",
            ),
        ),
        migrations.AddField(
            model_name="radiusaccounting",
            name="framed_ipv6_address",
            field=models.GenericIPAddressField(
                blank=True,
                db_column="framedipv6address",
                null=True,
                protocol="IPv6",
                verbose_name="framed IPv6 address",
            ),
        ),
        migrations.AddField(
            model_name="radiusaccounting",
            name="framed_ipv6_prefix",
            field=models.CharField(
                blank=True,
                db_column="framedipv6prefix",
                max_length=44,
                null=True,
                validators=[openwisp_radius.base.validators.ipv6_network_validator],
                verbose_name="framed IPv6 prefix",
            ),
        ),
        migrations.AddField(
            model_name="radiusaccounting",
            name="organization",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=swapper.get_model_name("openwisp_users", "Organization"),
                verbose_name="organization",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="radiuscheck",
            name="details",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="radiuscheck",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="radiuscheck",
            name="organization",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=swapper.get_model_name("openwisp_users", "Organization"),
                verbose_name="organization",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="radiuscheck",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="radiuscheck",
            name="valid_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="radiusgroupcheck",
            name="details",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="radiusgroupreply",
            name="details",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="radiuspostauth",
            name="details",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="radiuspostauth",
            name="organization",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=swapper.get_model_name("openwisp_users", "Organization"),
                verbose_name="organization",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="radiusreply",
            name="details",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="radiusreply",
            name="organization",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=swapper.get_model_name("openwisp_users", "Organization"),
                verbose_name="organization",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="radiusreply",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="radiususergroup",
            name="details",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="radiususergroup",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="nas",
            name="id",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, primary_key=True, serialize=False
            ),
        ),
        migrations.AlterField(
            model_name="radiusaccounting",
            name="called_station_id",
            field=models.CharField(
                blank=True,
                db_column="calledstationid",
                db_index=True,
                max_length=50,
                null=True,
                verbose_name="called station ID",
            ),
        ),
        migrations.AlterField(
            model_name="radiusaccounting",
            name="calling_station_id",
            field=models.CharField(
                blank=True,
                db_column="callingstationid",
                db_index=True,
                max_length=50,
                null=True,
                verbose_name="calling station ID",
            ),
        ),
        migrations.AlterField(
            model_name="radiusaccounting",
            name="framed_ip_address",
            field=models.GenericIPAddressField(
                blank=True,
                db_column="framedipaddress",
                null=True,
                verbose_name="framed IP address",
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
        migrations.AlterField(
            model_name="radiuscheck",
            name="id",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, primary_key=True, serialize=False
            ),
        ),
        migrations.AlterField(
            model_name="radiuscheck",
            name="username",
            field=models.CharField(
                blank=True, db_index=True, max_length=64, verbose_name="username"
            ),
        ),
        migrations.AlterField(
            model_name="radiusgroupcheck",
            name="groupname",
            field=models.CharField(
                blank=True, db_index=True, max_length=64, verbose_name="group name"
            ),
        ),
        migrations.AlterField(
            model_name="radiusgroupcheck",
            name="id",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, primary_key=True, serialize=False
            ),
        ),
        migrations.AlterField(
            model_name="radiusgroupreply",
            name="groupname",
            field=models.CharField(
                blank=True, db_index=True, max_length=64, verbose_name="group name"
            ),
        ),
        migrations.AlterField(
            model_name="radiusgroupreply",
            name="id",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, primary_key=True, serialize=False
            ),
        ),
        migrations.AlterField(
            model_name="radiuspostauth",
            name="id",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, primary_key=True, serialize=False
            ),
        ),
        migrations.AlterField(
            model_name="radiusreply",
            name="id",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, primary_key=True, serialize=False
            ),
        ),
        migrations.AlterField(
            model_name="radiusreply",
            name="username",
            field=models.CharField(
                blank=True, db_index=True, max_length=64, verbose_name="username"
            ),
        ),
        migrations.AlterField(
            model_name="radiususergroup",
            name="groupname",
            field=models.CharField(
                blank=True, max_length=64, verbose_name="group name"
            ),
        ),
        migrations.AlterField(
            model_name="radiususergroup",
            name="id",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, primary_key=True, serialize=False
            ),
        ),
        migrations.AlterField(
            model_name="radiususergroup",
            name="username",
            field=models.CharField(
                blank=True, db_index=True, max_length=64, verbose_name="username"
            ),
        ),
        migrations.CreateModel(
            name="RadiusToken",
            fields=[
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "key",
                    models.CharField(
                        max_length=40,
                        primary_key=True,
                        serialize=False,
                        verbose_name="Key",
                    ),
                ),
                (
                    "can_auth",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "Enable the radius token to be used for "
                            "freeradius authorization request"
                        ),
                    ),
                ),
                ("details", models.CharField(blank=True, max_length=64, null=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=swapper.get_model_name("openwisp_users", "Organization"),
                        verbose_name="organization",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="radius_token",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "radius token",
                "verbose_name_plural": "radius token",
                "db_table": "radiustoken",
                "abstract": False,
            },
            bases=(openwisp_users.mixins.ValidateOrgMixin, models.Model),
        ),
        migrations.CreateModel(
            name="RadiusGroup",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        db_index=True,
                        max_length=255,
                        unique=True,
                        verbose_name="group name",
                    ),
                ),
                (
                    "description",
                    models.CharField(
                        blank=True, max_length=64, null=True, verbose_name="description"
                    ),
                ),
                (
                    "default",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "The default group is automatically assigned "
                            "to new users; changing the default group has "
                            "only effect on new users (existing users will "
                            "keep being members of their current group)"
                        ),
                        verbose_name="is default?",
                    ),
                ),
                ("details", models.CharField(blank=True, max_length=64, null=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=swapper.get_model_name("openwisp_users", "Organization"),
                        verbose_name="organization",
                    ),
                ),
            ],
            options={
                "verbose_name": "group",
                "verbose_name_plural": "groups",
                "abstract": False,
            },
            bases=(openwisp_users.mixins.ValidateOrgMixin, models.Model),
        ),
        migrations.CreateModel(
            name="OrganizationRadiusSettings",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "token",
                    openwisp_utils.base.KeyField(
                        default=openwisp_utils.utils.get_random_key,
                        help_text=None,
                        max_length=32,
                        validators=[
                            django.core.validators.RegexValidator(
                                re.compile("^[^\\s/\\.]+$"),
                                code="invalid",
                                message=(
                                    "This value must not contain spaces, "
                                    "dots or slashes."
                                ),
                            )
                        ],
                    ),
                ),
                (
                    "sms_verification",
                    models.BooleanField(
                        blank=True,
                        default=None,
                        help_text=(
                            "whether users who sign up should be "
                            "required to verify their mobile "
                            "phone number via SMS"
                        ),
                        null=True,
                    ),
                ),
                (
                    "sms_sender",
                    models.CharField(
                        blank=True,
                        help_text=(
                            "alpha numeric identifier used as sender for "
                            "SMS sent by this organization"
                        ),
                        max_length=128,
                        null=True,
                        verbose_name="Sender",
                    ),
                ),
                (
                    "sms_meta_data",
                    jsonfield.fields.JSONField(
                        blank=True,
                        help_text=(
                            "Additional configuration for SMS backend in JSON format"
                            " (optional, leave blank if unsure)"
                        ),
                        null=True,
                        verbose_name="SMS meta data",
                    ),
                ),
                (
                    "freeradius_allowed_hosts",
                    models.TextField(
                        blank=True,
                        help_text=(
                            "Comma separated list of IP addresses allowed "
                            "to access freeradius API"
                        ),
                        null=True,
                    ),
                ),
                ("details", models.CharField(blank=True, max_length=64, null=True)),
                (
                    "organization",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="radius_settings",
                        to=swapper.get_model_name("openwisp_users", "Organization"),
                        verbose_name="organization",
                    ),
                ),
            ],
            options={
                "verbose_name": "Organization radius settings",
                "verbose_name_plural": "Organization radius settings",
                "abstract": False,
            },
        ),
        migrations.AddField(
            model_name="radiusgroupcheck",
            name="group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=swapper.get_model_name("openwisp_radius", "RadiusGroup"),
            ),
        ),
        migrations.AddField(
            model_name="radiusgroupreply",
            name="group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=swapper.get_model_name("openwisp_radius", "RadiusGroup"),
            ),
        ),
        migrations.AddField(
            model_name="radiususergroup",
            name="group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=swapper.get_model_name("openwisp_radius", "RadiusGroup"),
            ),
        ),
        migrations.AlterUniqueTogether(
            name="radiususergroup",
            unique_together={("user", "group")},
        ),
        migrations.CreateModel(
            name="RadiusBatch",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                (
                    "strategy",
                    models.CharField(
                        choices=[
                            ("prefix", "Generate from prefix"),
                            ("csv", "Import from CSV"),
                        ],
                        db_index=True,
                        help_text="Import users from a CSV or generate using a prefix",
                        max_length=16,
                        verbose_name="strategy",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        db_index=True,
                        help_text="A unique batch name",
                        max_length=128,
                        verbose_name="name",
                    ),
                ),
                (
                    "csvfile",
                    private_storage.fields.PrivateFileField(
                        blank=True,
                        help_text=(
                            "The csv file containing the user details to be uploaded"
                        ),
                        null=True,
                        storage=private_storage.storage.files.PrivateFileSystemStorage(
                            base_url=urljoin(RADIUS_API_BASEURL, CSV_URL_PATH),
                            location=settings.PRIVATE_STORAGE_ROOT,
                        ),
                        upload_to=openwisp_radius.base.models._get_csv_file_location,
                        verbose_name="CSV",
                    ),
                ),
                (
                    "prefix",
                    models.CharField(
                        blank=True,
                        help_text=(
                            "Usernames generated will be of the format [prefix][number]"
                        ),
                        max_length=20,
                        null=True,
                        verbose_name="prefix",
                    ),
                ),
                (
                    "user_credentials",
                    jsonfield.fields.JSONField(
                        blank=True, null=True, verbose_name="PDF"
                    ),
                ),
                (
                    "expiration_date",
                    models.DateField(
                        blank=True,
                        help_text="If left blank users will never expire",
                        null=True,
                        verbose_name="expiration date",
                    ),
                ),
                ("details", models.CharField(blank=True, max_length=64, null=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=swapper.get_model_name("openwisp_users", "Organization"),
                        verbose_name="organization",
                    ),
                ),
                (
                    "users",
                    models.ManyToManyField(
                        blank=True,
                        help_text="List of users uploaded in this batch",
                        related_name="radius_batch",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "batch user creation",
                "verbose_name_plural": "batch user creation operations",
                "db_table": "radbatch",
                "abstract": False,
                "unique_together": {("name", "organization")},
            },
            bases=(openwisp_users.mixins.ValidateOrgMixin, models.Model),
        ),
        migrations.CreateModel(
            name="PhoneToken",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                (
                    "valid_until",
                    models.DateTimeField(
                        default=openwisp_radius.utils.get_sms_default_valid_until
                    ),
                ),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("verified", models.BooleanField(default=False)),
                (
                    "token",
                    models.CharField(
                        default=openwisp_radius.utils.generate_sms_token,
                        editable=False,
                        max_length=8,
                    ),
                ),
                ("ip", models.GenericIPAddressField()),
                ("details", models.CharField(blank=True, max_length=64, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Phone verification token",
                "verbose_name_plural": "Phone verification tokens",
                "ordering": ("-created",),
                "abstract": False,
            },
        ),
        migrations.AddIndex(
            model_name="phonetoken",
            index=models.Index(
                fields=["user", "created"],
                name="sample_radi_user_id_b748c7_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="phonetoken",
            index=models.Index(
                fields=["user", "created", "ip"],
                name="sample_radi_user_id_044fca_idx",
            ),
        ),
    ]
