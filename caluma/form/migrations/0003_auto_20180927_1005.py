# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2018-09-27 10:05
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion
import localized_fields.fields.field


class Migration(migrations.Migration):

    dependencies = [("form", "0002_auto_20180910_1400")]

    operations = [
        migrations.CreateModel(
            name="Option",
            fields=[
                ("created", models.DateTimeField(auto_now_add=True)),
                ("modified", models.DateTimeField(auto_now=True)),
                ("slug", models.SlugField(primary_key=True, serialize=False)),
                (
                    "label",
                    localized_fields.fields.field.LocalizedField(required=["en"]),
                ),
                ("meta", django.contrib.postgres.fields.jsonb.JSONField(default={})),
            ],
            options={"abstract": False},
        ),
        migrations.CreateModel(
            name="QuestionOption",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("modified", models.DateTimeField(auto_now=True)),
                (
                    "sort",
                    models.PositiveIntegerField(
                        db_index=True, default=0, editable=False
                    ),
                ),
                (
                    "option",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="form.Option"
                    ),
                ),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="form.Question"
                    ),
                ),
            ],
            options={"ordering": ("-sort", "id")},
        ),
        migrations.AddField(
            model_name="question",
            name="options",
            field=models.ManyToManyField(
                related_name="questions",
                through="form.QuestionOption",
                to="form.Option",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="questionoption", unique_together=set([("option", "question")])
        ),
    ]