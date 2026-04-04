from django.conf import settings
from django.db import models


class BackupSetting(models.Model):
    FREQUENCY_HOURLY = 'hourly'
    FREQUENCY_DAILY = 'daily'
    FREQUENCY_WEEKLY = 'weekly'

    FREQUENCY_CHOICES = [
        (FREQUENCY_HOURLY, 'Hourly'),
        (FREQUENCY_DAILY, 'Daily'),
        (FREQUENCY_WEEKLY, 'Weekly'),
    ]

    auto_backup_enabled = models.BooleanField(default=False)
    backup_frequency = models.CharField(max_length=16, choices=FREQUENCY_CHOICES, default=FREQUENCY_DAILY)
    firebase_backup_prefix = models.CharField(max_length=255, default='system_backups')
    firebase_retention_count = models.PositiveIntegerField(default=30)
    last_backup_at = models.DateTimeField(null=True, blank=True)
    next_backup_at = models.DateTimeField(null=True, blank=True)
    last_backup_blob_path = models.CharField(max_length=500, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return 'Dashboard Backup Settings'


class BackupHistory(models.Model):
    TYPE_EXPORT_LOCAL = 'export_local'
    TYPE_BACKUP_FIREBASE = 'backup_firebase'
    TYPE_RESTORE = 'restore'
    TYPE_RESTORE_DRY_RUN = 'restore_dry_run'
    TYPE_COVERAGE_REPORT = 'coverage_report'

    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'

    TYPE_CHOICES = [
        (TYPE_EXPORT_LOCAL, 'Export Local'),
        (TYPE_BACKUP_FIREBASE, 'Backup Firebase'),
        (TYPE_RESTORE, 'Restore'),
        (TYPE_RESTORE_DRY_RUN, 'Restore Dry Run'),
        (TYPE_COVERAGE_REPORT, 'Coverage Report'),
    ]

    STATUS_CHOICES = [
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
    ]

    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES)
    destination = models.CharField(max_length=32, blank=True)
    blob_path = models.CharField(max_length=500, blank=True)
    file_size_bytes = models.PositiveBigIntegerField(default=0)
    integrity_ok = models.BooleanField(default=False)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)


class BackupAuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=120)
    metadata = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)