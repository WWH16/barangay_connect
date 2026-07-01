import os
import shutil
import sqlite3
import datetime
from django.conf import settings
from django.utils import timezone
from resident.models import DatabaseBackup, ActivityLog, User, BackupSettings

def perform_db_backup(user=None, backup_type='manual'):
    """
    Performs a database backup of the active SQLite database.
    Creates a new DatabaseBackup log record and saves the database copy.
    """
    # 1. Ensure the backups directory exists
    backups_dir = os.path.join(settings.BASE_DIR, 'backups')
    os.makedirs(backups_dir, exist_ok=True)

    # 2. Get active database configuration
    db_config = settings.DATABASES['default']
    if db_config['ENGINE'] != 'django.db.backends.sqlite3':
        raise ValueError("Backup utility currently only supports SQLite databases.")

    active_db_path = db_config['NAME']
    
    # 3. Create a unique filename
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f"backup_{backup_type}_{timestamp}.sqlite3"
    backup_path = os.path.join(backups_dir, filename)

    # 4. Perform backup using sqlite3.Connection.backup (thread-safe and handles concurrent access)
    try:
        src_conn = sqlite3.connect(active_db_path)
        dest_conn = sqlite3.connect(backup_path)
        with dest_conn:
            src_conn.backup(dest_conn)
        dest_conn.close()
        src_conn.close()

        # Get file size
        file_size = os.path.getsize(backup_path)

        # 5. Create backup record
        backup_record = DatabaseBackup.objects.create(
            filename=filename,
            file_path=backup_path,
            file_size=file_size,
            created_by=user,
            backup_type=backup_type,
            status='success'
        )

        # Log activity
        # If user is None, assign to the first official found, or system
        log_user = user
        if not log_user:
            log_user = User.objects.filter(role='official').first()
            
        if log_user:
            ActivityLog.objects.create(
                user=log_user,
                action=f"Created database backup: {filename} ({backup_type.capitalize()})"
            )

        return backup_record, None
    except Exception as e:
        # If backup file was partially created, clean it up
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except Exception:
                pass
        
        # Log failure
        error_msg = str(e)
        # Fallback user for logging
        log_user = user if user else User.objects.filter(role='official').first()
        
        backup_record = DatabaseBackup.objects.create(
            filename=filename,
            file_path=backup_path,
            file_size=0,
            created_by=user,
            backup_type=backup_type,
            status='failed',
            error_message=error_msg
        )
        return backup_record, error_msg


def restore_db_backup(backup_record, user):
    """
    Restores the database from a given DatabaseBackup record.
    Closes database connections, replaces the active SQLite file, and logs action.
    """
    backup_path = backup_record.file_path
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"Backup file not found on disk: {backup_path}")

    # Get active database path
    db_config = settings.DATABASES['default']
    active_db_path = db_config['NAME']

    from django.db import connections
    
    # 1. Close all active database connections to avoid file lock issues
    connections.close_all()

    # 2. Copy backup file over active database
    shutil.copy2(backup_path, active_db_path)

    # 3. Create activity log inside the newly restored database
    # Connections will automatically reopen when saving
    ActivityLog.objects.create(
        user=user,
        action=f"Restored database from backup: {backup_record.filename}"
    )


def get_backup_settings():
    """Retrieves the singleton BackupSettings or creates defaults."""
    settings, created = BackupSettings.objects.get_or_create(
        defaults={
            'backup_day': 'Sunday',
            'backup_time': datetime.time(2, 0)
        }
    )
    return settings


def get_most_recent_scheduled_datetime(day_name, time_obj):
    """
    Calculates the datetime of the most recent scheduled backup window.
    For example, if current is Wednesday and target is Sunday 02:00,
    the most recent scheduled time was last Sunday 02:00.
    """
    now = timezone.now()
    local_now = timezone.localtime(now)
    
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    try:
        target_weekday = days.index(day_name)
    except ValueError:
        target_weekday = 6 # Default to Sunday
        
    current_date = local_now.date()
    current_weekday = current_date.weekday()
    
    days_ago = (current_weekday - target_weekday) % 7
    scheduled_date = current_date - datetime.timedelta(days=days_ago)
    
    scheduled_dt = datetime.datetime.combine(scheduled_date, time_obj)
    scheduled_dt = timezone.make_aware(scheduled_dt, timezone.get_current_timezone())
    
    if scheduled_dt > local_now:
        scheduled_dt -= datetime.timedelta(days=7)
        
    return scheduled_dt


def check_and_run_weekly_backup():
    """
    Checks the user-defined backup schedule settings and runs the backup if due.
    If the current time has passed the scheduled backup window, and it hasn't run
    since that scheduled timestamp, it executes the backup.
    """
    settings = get_backup_settings()
    
    if not settings.auto_backup_enabled:
        return
    
    # Find when the backup should have most recently run
    target_dt = get_most_recent_scheduled_datetime(settings.backup_day, settings.backup_time)
    
    # Check if a scheduled backup succeeded since the target_dt
    recent_run = DatabaseBackup.objects.filter(
        backup_type='scheduled',
        status='success',
        created_at__gte=target_dt
    ).exists()
    
    # Check if settings.last_run has recorded this run
    if not recent_run or (settings.last_run is None or settings.last_run < target_dt):
        # Trigger the automated backup
        backup, error = perform_db_backup(user=None, backup_type='scheduled')
        if not error and backup.status == 'success':
            settings.last_run = timezone.now()
            settings.save()
