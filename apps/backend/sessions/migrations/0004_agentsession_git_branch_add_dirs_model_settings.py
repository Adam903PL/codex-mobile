from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("agent_sessions", "0003_agentsession_approval_policy_agentsession_model_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentsession",
            name="add_dirs",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="agentsession",
            name="git_branch",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="agentsession",
            name="model_settings",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
