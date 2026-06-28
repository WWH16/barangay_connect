from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from .models import Profile, Report


def login_view(request):
    """Handle login and registration. Redirect based on role after login."""
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'login':
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '')

            # Django auth uses username, so look up by email
            try:
                user_obj = User.objects.get(email=email)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None

            if user is not None:
                auth_login(request, user)
                return _redirect_by_role(user)
            else:
                messages.error(request, 'Invalid email or password.')

        elif action == 'register':
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            contact_number = request.POST.get('contact_number', '').strip()
            password = request.POST.get('password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if not first_name or not last_name or not email or not password or not confirm_password:
                messages.error(request, 'All fields are required.')
            elif password != confirm_password:
                messages.error(request, 'Passwords do not match.')
            elif User.objects.filter(email=email).exists():
                messages.error(request, 'An account with this email already exists.')
            elif len(password) < 6:
                messages.error(request, 'Password must be at least 6 characters.')
            else:
                # Create user — use email prefix for username
                username = email.split('@')[0]
                base_username = username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                )
                
                # Fetch profile created by signal and update contact_number
                profile, _ = Profile.objects.get_or_create(user=user)
                profile.contact_number = contact_number
                profile.save()

                auth_login(request, user)
                messages.success(request, 'Account created successfully! Welcome to Barangay Connect.')
                return redirect('resident_dashboard')

    return render(request, 'resident/login.html')


def logout_view(request):
    """Log the user out and redirect to login."""
    auth_logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


@login_required(login_url='login')
def resident_dashboard(request):
    """Dashboard for residents — shows their submitted reports."""
    profile = _get_or_create_profile(request.user)
    if profile.is_staff_or_official:
        return redirect('staff_dashboard')

    reports = Report.objects.filter(resident=request.user)
    context = {
        'user': request.user,
        'reports': reports,
        'total_reports': reports.count(),
        'pending_count': reports.filter(status='Pending').count(),
        'resolved_count': reports.filter(status='Resolved').count(),
    }
    return render(request, 'resident/dashboard.html', context)


@login_required(login_url='login')
def submit_report(request):
    """Allow residents to submit a new report."""
    profile = _get_or_create_profile(request.user)
    if profile.is_staff_or_official:
        return redirect('staff_dashboard')

    if request.method == 'POST':
        report_type = request.POST.get('report_type')
        category = request.POST.get('category', '').strip()
        description = request.POST.get('description', '').strip()

        if report_type == 'complaint':
            title = request.POST.get('title', '').strip()
            evidence = request.FILES.get('evidence')
            
            if title and category and description:
                Report.objects.create(
                    resident=request.user,
                    report_type='complaint',
                    category=category,
                    title=title,
                    description=description,
                    evidence=evidence
                )
                messages.success(request, 'Complaint submitted successfully!')
                return redirect('resident_dashboard')
            else:
                messages.error(request, 'Please fill in all required fields.')

        elif report_type == 'incident':
            location = request.POST.get('location', '').strip()
            evidence = request.FILES.get('evidence')
            
            if category and location and description:
                title = f"Incident: {category} at {location}"
                Report.objects.create(
                    resident=request.user,
                    report_type='incident',
                    category=category,
                    title=title,
                    description=description,
                    location=location,
                    evidence=evidence
                )
                messages.success(request, 'Incident reported successfully!')
                return redirect('resident_dashboard')
            else:
                messages.error(request, 'Please fill in all required fields.')
        else:
            messages.error(request, 'Invalid report type.')

    return render(request, 'resident/submit_report.html')


# ---------- helpers ----------

def _get_or_create_profile(user):
    """Get or create profile for a user (handles superusers without profile)."""
    profile, _ = Profile.objects.get_or_create(user=user, defaults={'role': 'resident'})
    return profile


def _redirect_by_role(user):
    """Redirect user to the correct dashboard based on their role."""
    profile = _get_or_create_profile(user)
    if profile.is_staff_or_official:
        return redirect('staff_dashboard')
    return redirect('resident_dashboard')