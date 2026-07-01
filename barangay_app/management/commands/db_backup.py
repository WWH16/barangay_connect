from django.core.management.base import BaseCommand
from barangay_app.backup_utils import perform_db_backup

class Command(BaseCommand):
    help = 'Performs a database backup for Barangay Connect'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='scheduled',
            choices=['manual', 'scheduled'],
            help='Type of the backup (manual or scheduled)'
        )

    def handle(self, *args, **options):
        backup_type = options['type']
        self.stdout.write(f"Initiating {backup_type} database backup...")
        
        backup, error = perform_db_backup(user=None, backup_type=backup_type)
        
        if error:
            self.stderr.write(f"Backup failed: {error}")
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully created backup: {backup.filename}"))
