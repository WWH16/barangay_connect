from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Complaint, Incident, EvidenceFile, CaseAssignment, Notification, ActivityLog

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'status', 'is_staff', 'is_superuser')
    list_filter = ('role', 'status', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    
    # Keep the primary key as user_id
    filter_horizontal = ()
    
    # Inject custom fields into default fields editing sections in django admin
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Barangay Profile', {'fields': ('role', 'contact_number', 'status')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Barangay Profile', {'fields': ('role', 'contact_number', 'status')}),
    )

@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('complaint_id', 'title', 'user', 'status', 'date_submitted')
    list_filter = ('status', 'date_submitted')
    search_fields = ('title', 'user__username')

@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ('incident_id', 'category', 'user', 'location', 'status', 'date_reported')
    list_filter = ('status', 'date_reported')
    search_fields = ('category', 'location', 'user__username')

@admin.register(EvidenceFile)
class EvidenceFileAdmin(admin.ModelAdmin):
    list_display = ('file_id', 'complaint', 'incident', 'file_type', 'uploaded_at')

@admin.register(CaseAssignment)
class CaseAssignmentAdmin(admin.ModelAdmin):
    list_display = ('assignment_id', 'case_type', 'case_id', 'assigned_to', 'assigned_by', 'status')
    list_filter = ('case_type', 'status')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('notification_id', 'user', 'message', 'created_at')

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('log_id', 'user', 'action', 'timestamp')
