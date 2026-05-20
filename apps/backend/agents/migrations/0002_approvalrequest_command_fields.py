from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("agents", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="approvalrequest",
            name="arguments",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="approvalrequest",
            name="command_id",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="approvalrequest",
            name="exit_code",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="approvalrequest",
            name="finished_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="approvalrequest",
            name="started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="approvalrequest",
            name="stderr",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="approvalrequest",
            name="stdout",
            field=models.TextField(blank=True),
        ),
    ]
