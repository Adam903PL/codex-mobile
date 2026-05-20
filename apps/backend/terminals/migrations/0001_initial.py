from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("devices", "0001_initial"),
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TerminalSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("claimed", "Claimed"), ("running", "Running"), ("exited", "Exited"), ("killed", "Killed"), ("failed", "Failed")], default="queued", max_length=20)),
                ("cwd", models.CharField(max_length=500)),
                ("shell", models.CharField(default="pwsh", max_length=40)),
                ("cols", models.PositiveIntegerField(default=96)),
                ("rows", models.PositiveIntegerField(default=28)),
                ("exit_code", models.IntegerField(blank=True, null=True)),
                ("error_code", models.CharField(blank=True, max_length=80)),
                ("error_message", models.TextField(blank=True)),
                ("kill_requested", models.BooleanField(default=False)),
                ("claimed_at", models.DateTimeField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("last_activity_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="terminal_sessions", to="devices.device")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="terminal_sessions", to=settings.AUTH_USER_MODEL)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="terminal_sessions", to="projects.project")),
            ],
            options={
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="TerminalEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("sequence", models.PositiveIntegerField()),
                ("kind", models.CharField(choices=[("ready", "Ready"), ("status", "Status"), ("output", "Output"), ("stderr", "Stderr"), ("cwd", "Cwd"), ("exit", "Exit"), ("error", "Error")], max_length=20)),
                ("stream", models.CharField(blank=True, max_length=20)),
                ("data", models.TextField(blank=True)),
                ("cwd", models.CharField(blank=True, max_length=500)),
                ("exit_code", models.IntegerField(blank=True, null=True)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="terminals.terminalsession")),
            ],
            options={
                "ordering": ["sequence"],
            },
        ),
        migrations.CreateModel(
            name="TerminalInput",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("sequence", models.PositiveIntegerField()),
                ("kind", models.CharField(choices=[("stdin", "Stdin"), ("resize", "Resize"), ("kill", "Kill")], max_length=20)),
                ("data", models.TextField(blank=True)),
                ("cols", models.PositiveIntegerField(blank=True, null=True)),
                ("rows", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="inputs", to="terminals.terminalsession")),
            ],
            options={
                "ordering": ["sequence"],
            },
        ),
        migrations.AddIndex(
            model_name="terminalsession",
            index=models.Index(fields=["owner", "-updated_at"], name="terminal_owner_updated_idx"),
        ),
        migrations.AddIndex(
            model_name="terminalsession",
            index=models.Index(fields=["device", "status", "created_at"], name="terminal_device_queue_idx"),
        ),
        migrations.AddIndex(
            model_name="terminalevent",
            index=models.Index(fields=["session", "sequence"], name="terminal_event_sequence_idx"),
        ),
        migrations.AddIndex(
            model_name="terminalinput",
            index=models.Index(fields=["session", "sequence"], name="terminal_input_sequence_idx"),
        ),
        migrations.AddConstraint(
            model_name="terminalevent",
            constraint=models.UniqueConstraint(fields=("session", "sequence"), name="unique_terminal_event_sequence"),
        ),
        migrations.AddConstraint(
            model_name="terminalinput",
            constraint=models.UniqueConstraint(fields=("session", "sequence"), name="unique_terminal_input_sequence"),
        ),
    ]
