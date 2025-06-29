# Generated by Django 5.2.3 on 2025-06-29 10:10

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_event_comment_event_is_done'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='category',
            field=models.CharField(choices=[('exam', 'Exam Day'), ('midterm', 'Mid-Term Break'), ('holiday', 'Holiday'), ('sports', 'Games/Sports Day'), ('other', 'Other')], default='other', max_length=20),
        ),
        migrations.AddField(
            model_name='event',
            name='term',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='events', to='core.term'),
        ),
    ]
