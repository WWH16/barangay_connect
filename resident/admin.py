from django.contrib import admin
from .models import Profile, Report


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'resident', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'resident__username')
