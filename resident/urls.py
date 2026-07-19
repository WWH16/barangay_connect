from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.resident_dashboard, name='resident_dashboard'),
    path('submit-report/', views.submit_report, name='submit_report'),
]
