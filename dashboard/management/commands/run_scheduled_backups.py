from django.core.management.base import BaseCommand
from django.utils import timezone

from dashboard.models import BackupSetting, BackupHistory
from dashboard.views import (
    build_backup_json,
    upload_backup_json_to_firebase,
    compute_next_backup_time,
    validate_backup_json_content,
    apply_firebase_backup_retention,
    log_backup_history,
    log_backup_audit,
)


class Command(BaseCommand):
    help = 'Run due automatic dashboard backups and upload JSON to Firebase.'

    def handle(self, *args, **options):
        setting = BackupSetting.objects.filter(pk=1, auto_backup_enabled=True).first()
        if not setting:
            self.stdout.write(self.style.WARNING('Auto backup is disabled or not configured.'))
            return

        now = timezone.now()
        if setting.next_backup_at and setting.next_backup_at > now:
            self.stdout.write(self.style.WARNING(f'No backup due yet. Next run at {setting.next_backup_at}.'))
            return

        try:
            content = build_backup_json()
            integrity_ok, integrity_error, summary = validate_backup_json_content(content)
            if not integrity_ok:
                raise ValueError(integrity_error)
            blob_path = upload_backup_json_to_firebase(content, setting.firebase_backup_prefix)
            removed_paths = apply_firebase_backup_retention(setting.firebase_backup_prefix, setting.firebase_retention_count)
        except Exception as exc:
            log_backup_history(
                request_user=None,
                action_type=BackupHistory.TYPE_BACKUP_FIREBASE,
                status=BackupHistory.STATUS_FAILED,
                destination='firebase',
                integrity_ok=False,
                details=str(exc),
            )
            self.stdout.write(self.style.ERROR(f'Backup failed: {exc}'))
            return

        setting.last_backup_at = now
        setting.last_backup_blob_path = blob_path
        setting.next_backup_at = compute_next_backup_time(now, setting.backup_frequency)
        setting.save(update_fields=['last_backup_at', 'last_backup_blob_path', 'next_backup_at', 'updated_at'])

        detail_text = (
            f"Records: {summary.get('total_records', 0)}, Models: {summary.get('total_models', 0)}, "
            f"Retention removed: {len(removed_paths)}"
        )
        log_backup_history(
            request_user=None,
            action_type=BackupHistory.TYPE_BACKUP_FIREBASE,
            status=BackupHistory.STATUS_SUCCESS,
            destination='firebase',
            blob_path=blob_path,
            file_size_bytes=len(content.encode('utf-8')),
            integrity_ok=True,
            details=detail_text,
        )
        log_backup_audit(
            request_user=None,
            action='Scheduled backup run',
            metadata=f'{blob_path} | {detail_text}',
        )

        self.stdout.write(self.style.SUCCESS(f'Backup uploaded: {blob_path}'))
        self.stdout.write(self.style.SUCCESS(f'Next backup at: {setting.next_backup_at}'))
