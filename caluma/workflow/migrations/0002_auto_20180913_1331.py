# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2018-09-13 13:31
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("workflow", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="taskspecification",
            name="type",
            field=models.CharField(
                choices=[("simple", "Task which can only be marked as completed.")],
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="workflowspecification",
            name="start",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="workflow.TaskSpecification",
            ),
        ),
    ]