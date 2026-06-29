from django.urls import path
from . import views

urlpatterns = [
    path('staff/dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('staff/assign-report/<int:report_id>/', views.assign_report, name='assign_report'),
    path('staff/update-report-status/<int:report_id>/', views.update_report_status, name='update_report_status'),
    path('staff/update-report-remarks/<int:report_id>/', views.update_report_remarks, name='update_report_remarks'),
    path('official/reports/', views.official_reports, name='official_reports'),

]
