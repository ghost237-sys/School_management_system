# Generated by Django 5.2.3 on 2025-07-01 09:44

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_remove_exam_classes_remove_exam_subjects'),
    ]

    operations = [
        migrations.CreateModel(
            name='Fee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('level', models.CharField(max_length=50)),
                ('description', models.CharField(blank=True, max_length=255, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('term', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fees', to='core.term')),
            ],
        ),
        migrations.CreateModel(
            name='StudentFeeAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_paid', models.BooleanField(default=False)),
                ('paid_on', models.DateField(blank=True, null=True)),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('fee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='student_assignments', to='core.fee')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fee_assignments', to='core.student')),
            ],
        ),
    ]
