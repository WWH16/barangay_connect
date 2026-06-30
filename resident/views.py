from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.conf import settings
import requests
from .models import User, Complaint, Incident, EvidenceFile, CaseAssignment, Notification, ActivityLog
from barangay_app.email_utils import send_resident_notification

User = get_user_model()

def verify_recaptcha(request):
    """Verify the reCAPTCHA v3 token."""
    recaptcha_response = request.POST.get('g-recaptcha-response')
    if not recaptcha_response:
        return False
        
    data = {
        'secret': settings.RECAPTCHA_SECRET_KEY,
        'response': recaptcha_response
    }
    
    try:
        r = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
        result = r.json()
        # Ensure it was successful and the score is decent (>= 0.5)
        if result.get('success') and result.get('score', 0) >= 0.5:
            return True
    except Exception:
        pass
    
    return False


def login_view(request):
    """Handle login and registration. Redirect based on role after login."""
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Verify reCAPTCHA
        if not verify_recaptcha(request):
            messages.error(request, 'reCAPTCHA verification failed. Please try again.')
            return render(request, 'resident/login.html', {'recaptcha_site_key': settings.RECAPTCHA_SITE_KEY})

        if action == 'login':
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '')

            try:
                user_obj = User.objects.get(email=email)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None

            if user is not None:
                auth_login(request, user)
                # Log activity
                ActivityLog.objects.create(user=user, action="Logged into the system.")
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
                    role='resident',
                    contact_number=contact_number
                )
                
                # Log activity
                ActivityLog.objects.create(user=user, action="Registered a new account.")
                auth_login(request, user)
                messages.success(request, 'Account created successfully! Welcome to Barangay Connect.')
                return redirect('resident_dashboard')

    return render(request, 'resident/login.html', {'recaptcha_site_key': settings.RECAPTCHA_SITE_KEY})


def logout_view(request):
    """Log the user out and redirect to login."""
    if request.user.is_authenticated:
        ActivityLog.objects.create(user=request.user, action="Logged out of the system.")
    auth_logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


@login_required(login_url='login')
def resident_dashboard(request):
    """Dashboard for residents — shows their submitted reports (complaints & incidents) unified."""
    if request.user.is_staff_or_official:
        return redirect('staff_dashboard')

    # Fetch user's complaints
    complaints = Complaint.objects.filter(user=request.user)
    # Fetch user's incidents
    incidents = Incident.objects.filter(user=request.user)

    # Combine into a unified dashboard list matching dashboard templates
    reports = []
    for c in complaints:
        # Get evidence file if any
        evidence_file = c.evidence.first()
        reports.append({
            'id': c.complaint_id,
            'title': c.title,
            'description': c.description,
            'status': c.status,
            'remarks': c.remarks,
            'report_type': 'complaint',
            'created_at': c.date_submitted,
            'category': c.category,
            'latitude': c.latitude,
            'longitude': c.longitude,
            'evidence': evidence_file.file_path if evidence_file else None,
        })
    for i in incidents:
        evidence_file = i.evidence.first()
        reports.append({
            'id': i.incident_id,
            'title': f"Incident: {i.category} at {i.location}",
            'description': i.description,
            'status': i.status,
            'remarks': i.remarks,
            'report_type': 'incident',
            'created_at': i.date_reported,
            'category': i.category,
            'location': i.location,
            'latitude': i.latitude,
            'longitude': i.longitude,
            'evidence': evidence_file.file_path if evidence_file else None,
        })
        
    reports.sort(key=lambda x: x['created_at'], reverse=True)

    # Get user notifications and populate display attributes
    notifications_qs = Notification.objects.filter(user=request.user).order_by('-created_at')[:6]
    notifications = []
    for n in notifications_qs:
        msg = n.message.lower()
        if 'resolved' in msg:
            notif_type = 'success'
            icon = 'check-circle'
            notif_title = "Case Resolved"
        elif 'assigned' in msg or 'investigated' in msg or 'processed' in msg:
            notif_type = 'info'
            icon = 'shield'
            notif_title = "Personnel Assigned"
        elif 'update' in msg or 'remark' in msg:
            notif_type = 'warning'
            icon = 'message-square'
            notif_title = "Official Case Update"
        elif 'submitted' in msg or 'filed' in msg:
            notif_type = 'info'
            icon = 'file-plus'
            notif_title = "Report Filed Successfully"
        else:
            notif_type = 'default'
            icon = 'bell'
            notif_title = "Notification Alert"
            
        notifications.append({
            'title': notif_title,
            'message': n.message,
            'date': n.created_at,
            'type': notif_type,
            'icon': icon
        })


    context = {
        'user': request.user,
        'reports': reports,
        'total_reports': len(reports),
        'pending_count': sum(1 for r in reports if r['status'] == 'Pending'),
        'resolved_count': sum(1 for r in reports if r['status'] == 'Resolved'),
        'notifications': notifications,
    }
    return render(request, 'resident/dashboard.html', context)



@login_required(login_url='login')
def submit_report(request):
    """Allow residents to submit a new report (complaint or incident)."""
    if request.user.is_staff_or_official:
        return redirect('staff_dashboard')

    if request.method == 'POST':
        # Verify reCAPTCHA
        if not verify_recaptcha(request):
            messages.error(request, 'reCAPTCHA verification failed. Please try again.')
            return render(request, 'resident/submit_report.html', {'recaptcha_site_key': settings.RECAPTCHA_SITE_KEY})
            
        report_type = request.POST.get('report_type')
        category = request.POST.get('category', '').strip()
        description = request.POST.get('description', '').strip()
        evidence = request.FILES.get('evidence')

        if report_type == 'complaint':
            title = request.POST.get('title', '').strip()
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            
            if title and category and description:
                complaint = Complaint.objects.create(
                    user=request.user,
                    category=category,
                    title=title,
                    description=description,
                    latitude=float(latitude) if latitude else None,
                    longitude=float(longitude) if longitude else None
                )
                
                if evidence:
                    file_type = evidence.content_type or 'document/unknown'
                    EvidenceFile.objects.create(
                        complaint=complaint,
                        file_path=evidence,
                        file_type=file_type
                    )
                
                # Log activity
                ActivityLog.objects.create(
                    user=request.user,
                    action=f"Submitted complaint '{title}' (ID: #{complaint.complaint_id})"
                )
                
                messages.success(request, 'Complaint submitted successfully!')
                return redirect('resident_dashboard')
            else:
                messages.error(request, 'Please fill in all required fields.')

        elif report_type == 'incident':
            location = request.POST.get('location', '').strip()
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            
            if category and location and description:
                incident = Incident.objects.create(
                    user=request.user,
                    category=category,
                    location=location,
                    description=description,
                    latitude=float(latitude) if latitude else None,
                    longitude=float(longitude) if longitude else None
                )
                
                if evidence:
                    file_type = evidence.content_type or 'document/unknown'
                    EvidenceFile.objects.create(
                        incident=incident,
                        file_path=evidence,
                        file_type=file_type
                    )
                
                # Log activity
                ActivityLog.objects.create(
                    user=request.user,
                    action=f"Submitted incident report '{category}' (ID: #{incident.incident_id})"
                )
                
                messages.success(request, 'Incident reported successfully!')
                return redirect('resident_dashboard')
            else:
                messages.error(request, 'Please fill in all required fields.')
        else:
            messages.error(request, 'Invalid report type.')

    return render(request, 'resident/submit_report.html', {'recaptcha_site_key': settings.RECAPTCHA_SITE_KEY})


# ---------- helpers ----------

def _redirect_by_role(user):
    """Redirect user to the correct dashboard based on their role."""
    if user.is_staff_or_official:
        return redirect('staff_dashboard')
    return redirect('resident_dashboard')