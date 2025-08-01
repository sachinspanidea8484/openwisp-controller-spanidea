# Generated by Django 2.2.9 on 2019-12-22 16:39

from django.db import migrations, models

import openwisp_radius.base.validators


class Migration(migrations.Migration):
    dependencies = [("openwisp_radius", "0005_radiustoken")]

    operations = [
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
    ]
