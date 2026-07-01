from django.urls import path
from . import views

urlpatterns = [
    path('staff/dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('staff/assign-report/<int:report_id>/', views.assign_report, name='assign_report'),
    path('staff/update-report-status/<int:report_id>/', views.update_report_status, name='update_report_status'),
    path('staff/update-report-remarks/<int:report_id>/', views.update_report_remarks, name='update_report_remarks'),
    path('official/reports/', views.official_reports, name='official_reports'),
    path('official/users/', views.user_management, name='user_management'),
    path('official/users/add/', views.add_user, name='add_user'),
    path('official/users/edit/<int:target_user_id>/', views.edit_user, name='edit_user'),
    path('official/activity-log/', views.activity_log_view, name='activity_log'),

    # Backup & Recovery endpoints
    path('official/backup-recovery/', views.backup_recovery_view, name='backup_recovery'),
    path('official/backup-recovery/create/', views.create_backup_view, name='create_backup'),
    path('official/backup-recovery/download/<int:backup_id>/', views.download_backup_view, name='download_backup'),
    path('official/backup-recovery/restore/<int:backup_id>/', views.restore_backup_view, name='restore_backup'),
    path('official/backup-recovery/delete/<int:backup_id>/', views.delete_backup_view, name='delete_backup'),
    path('official/backup-recovery/upload/', views.upload_backup_view, name='upload_backup'),
    path('official/backup-recovery/update-settings/', views.update_backup_settings_view, name='update_backup_settings'),

    # Email SMTP test endpoint
    path('staff/test-email/', views.test_email_view, name='test_email'),
]
