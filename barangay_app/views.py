from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.http import JsonResponse, FileResponse, Http404
import os
from django.utils import timezone
from django.conf import settings
from resident.models import User, Complaint, Incident, EvidenceFile, CaseAssignment, Notification, ActivityLog, DatabaseBackup, BackupSettings
from barangay_app.email_utils import send_case_assigned_email, send_status_update_email, send_test_email, send_resident_notification, send_report_updated_email

User = get_user_model()


@login_required(login_url='login')
def staff_dashboard(request):
    """Dashboard for barangay staff and officials — shows all reports from residents."""
    if request.user.is_resident:
        return redirect('resident_dashboard')

    # Fetch complaints and incidents based on role
    if request.user.role == 'official':
        complaints_qs = Complaint.objects.all()
        incidents_qs = Incident.objects.all()
    else:
        # Staff can see cases assigned to them
        assigned_complaint_ids = CaseAssignment.objects.filter(assigned_to=request.user, case_type='complaint').values_list('case_id', flat=True)
        assigned_incident_ids = CaseAssignment.objects.filter(assigned_to=request.user, case_type='incident').values_list('case_id', flat=True)
        complaints_qs = Complaint.objects.filter(complaint_id__in=assigned_complaint_ids)
        incidents_qs = Incident.objects.filter(incident_id__in=assigned_incident_ids)

    # Fetch all assignments to map assigned staff
    assignments = CaseAssignment.objects.all()
    assignment_map = {}
    for a in assignments:
        assignment_map[(a.case_type, a.case_id)] = a.assigned_to

    # Build unified reports list
    reports = []
    for c in complaints_qs:
        evidence_file = c.evidence.first()
        reports.append({
            'id': c.complaint_id,
            'title': c.title,
            'description': c.description,
            'category': c.category,
            'status': c.status,
            'remarks': c.remarks,
            'report_type': 'complaint',
            'created_at': c.date_submitted,
            'resident': c.user,
            'latitude': c.latitude,
            'longitude': c.longitude,
            'evidence': evidence_file.file_path if evidence_file else None,
            'assigned_to': assignment_map.get(('complaint', c.complaint_id)),
        })
    for i in incidents_qs:
        evidence_file = i.evidence.first()
        reports.append({
            'id': i.incident_id,
            'title': f"Incident: {i.category} at {i.location}",
            'description': i.description,
            'category': i.category,
            'status': i.status,
            'remarks': i.remarks,
            'report_type': 'incident',
            'created_at': i.date_reported,
            'resident': i.user,
            'location': i.location,
            'latitude': i.latitude,
            'longitude': i.longitude,
            'evidence': evidence_file.file_path if evidence_file else None,
            'assigned_to': assignment_map.get(('incident', i.incident_id)),
        })

    reports.sort(key=lambda x: x['created_at'], reverse=True)

    # Get all staff members for the assignment dropdown
    staff_members = User.objects.filter(role='staff')

    context = {
        'user': request.user,
        'reports': reports,
        'staff_members': staff_members,
        'total_reports': len(reports),
        'pending_count': sum(1 for r in reports if r['status'] == 'Pending'),
        'in_progress_count': sum(1 for r in reports if r['status'] == 'In Progress'),
        'resolved_count': sum(1 for r in reports if r['status'] == 'Resolved'),
    }
    return render(request, 'barangay_app/dashboard.html', context)


@login_required(login_url='login')
def assign_report(request, report_id):
    """Assign a case (complaint or incident) to a staff member. Only officials can assign."""
    if request.user.role != 'official':
        messages.error(request, 'Only Barangay Officials can assign reports.')
        return redirect('staff_dashboard')

    if request.method == 'POST':
        case_type = request.POST.get('report_type')  # 'complaint' or 'incident'
        staff_id = request.POST.get('staff_id')

        if case_type == 'complaint':
            case_obj = get_object_or_404(Complaint, complaint_id=report_id)
            resident_user = case_obj.user
        else:
            case_obj = get_object_or_404(Incident, incident_id=report_id)
            resident_user = case_obj.user

        if staff_id:
            try:
                staff_user = User.objects.get(user_id=staff_id, role='staff')
                
                # Create or update assignment
                CaseAssignment.objects.update_or_create(
                    case_type=case_type,
                    case_id=report_id,
                    defaults={
                        'assigned_to': staff_user,
                        'assigned_by': request.user,
                        'status': 'In Progress'
                    }
                )
                
                # Update case status
                case_obj.status = 'In Progress'
                case_obj.save()
                
                # Notify resident and staff
                Notification.objects.create(
                    user=resident_user,
                    message=f"Your {case_type} (ID: #{report_id}) has been assigned to staff member {staff_user.get_full_name() or staff_user.username} by {request.user.get_full_name() or request.user.username} ({request.user.get_role_display()})."
                )
                Notification.objects.create(
                    user=staff_user,
                    message=f"You have been assigned to investigate {case_type} (ID: #{report_id}) by {request.user.get_full_name() or request.user.username}."
                )
                
                # Log activity
                ActivityLog.objects.create(
                    user=request.user,
                    action=f"Assigned {case_type} #{report_id} to staff {staff_user.username}"
                )
                
                # ── Send email notification to staff and resident ──
                send_case_assigned_email(
                    case_obj=case_obj,
                    case_type=case_type,
                    staff_user=staff_user,
                    assigned_by=request.user,
                )
                
                messages.success(request, f'Case assigned to {staff_user.get_full_name() or staff_user.username}.')
            except User.DoesNotExist:
                messages.error(request, 'Selected staff member not found.')
        else:
            # Delete assignment
            CaseAssignment.objects.filter(case_type=case_type, case_id=report_id).delete()
            case_obj.status = 'Pending'
            case_obj.save()
            
            # Notify resident
            Notification.objects.create(
                user=resident_user,
                message=f"Your {case_type} (ID: #{report_id}) is now unassigned by {request.user.get_full_name() or request.user.username} ({request.user.get_role_display()})."
            )
            # Log activity
            ActivityLog.objects.create(
                user=request.user,
                action=f"Unassigned {case_type} #{report_id}"
            )
            messages.success(request, 'Case unassigned.')

    return redirect('staff_dashboard')


@login_required(login_url='login')
def update_report_status(request, report_id):
    """Update report status. Staff can only update reports assigned to them or if they are officials."""
    if not request.user.is_staff_or_official:
        messages.error(request, 'Access denied.')
        return redirect('resident_dashboard')

    if request.method == 'POST':
        case_type = request.POST.get('report_type')  # 'complaint' or 'incident'
        new_status = request.POST.get('status')
        
        if case_type == 'complaint':
            case_obj = get_object_or_404(Complaint, complaint_id=report_id)
            resident_user = case_obj.user
        else:
            case_obj = get_object_or_404(Incident, incident_id=report_id)
            resident_user = case_obj.user

        # Security check: if staff (but not official), must be assigned
        if request.user.role == 'staff':
            is_assigned = CaseAssignment.objects.filter(case_type=case_type, case_id=report_id, assigned_to=request.user).exists()
            if not is_assigned:
                messages.error(request, 'You can only update cases assigned to you.')
                return redirect('staff_dashboard')

        if new_status in ['Pending', 'In Progress', 'Resolved']:
            case_obj.status = new_status
            case_obj.save()
            
            # Update assignment status if exists
            CaseAssignment.objects.filter(case_type=case_type, case_id=report_id).update(status=new_status)
            
            # Notify resident
            Notification.objects.create(
                user=resident_user,
                message=f"Your {case_type} (ID: #{report_id}) status has been updated to '{new_status}' by {request.user.get_full_name() or request.user.username} ({request.user.get_role_display()})."
            )
            # Log activity
            ActivityLog.objects.create(
                user=request.user,
                action=f"Updated status of {case_type} #{report_id} to {new_status}"
            )
            
            # ── Send email notification to the resident ──
            send_status_update_email(
                case_obj=case_obj,
                case_type=case_type,
                new_status=new_status,
                updater_user=request.user,
            )
            
            messages.success(request, f'Status updated to {new_status}.')
        else:
            messages.error(request, 'Invalid status choice.')

    return redirect('staff_dashboard')


@login_required(login_url='login')
def update_report_remarks(request, report_id):
    """Update case remarks. Staff can only update reports assigned to them or if they are officials."""
    if not request.user.is_staff_or_official:
        messages.error(request, 'Access denied.')
        return redirect('resident_dashboard')

    if request.method == 'POST':
        case_type = request.POST.get('report_type')  # 'complaint' or 'incident'
        new_remarks = request.POST.get('remarks', '').strip()
        
        if case_type == 'complaint':
            case_obj = get_object_or_404(Complaint, complaint_id=report_id)
            resident_user = case_obj.user
        else:
            case_obj = get_object_or_404(Incident, incident_id=report_id)
            resident_user = case_obj.user

        # Security check: if staff (but not official), must be assigned
        if request.user.role == 'staff':
            is_assigned = CaseAssignment.objects.filter(case_type=case_type, case_id=report_id, assigned_to=request.user).exists()
            if not is_assigned:
                messages.error(request, 'You can only update cases assigned to you.')
                return redirect('staff_dashboard')

        case_obj.remarks = new_remarks
        case_obj.save()
        
        # Notify resident
        Notification.objects.create(
            user=resident_user,
            message=f"Official update added to your {case_type} (ID: #{report_id}) by {request.user.get_full_name() or request.user.username} ({request.user.get_role_display()}): \"{new_remarks}\""
        )
        # Log activity
        ActivityLog.objects.create(
            user=request.user,
            action=f"Added case remarks to {case_type} #{report_id}"
        )
        
        # Send resident email notification
        if resident_user.email:
            send_resident_notification(
                to_email=resident_user.email,
                subject=f'Official update added to your {case_type}',
                template_name='notification.html',
                context={
                    'subject': f'Official update added to your {case_type} (ID: #{report_id})',
                    'recipient_name': resident_user.get_full_name() or resident_user.username,
                    'message_body': f'An official update has been added to your {case_type} by {request.user.get_full_name() or request.user.username} ({request.user.get_role_display()}):\n\n"{new_remarks}"',
                }
            )
        
        messages.success(request, 'Remarks updated successfully.')

    return redirect('staff_dashboard')


@login_required(login_url='login')
def official_reports(request):
    """Analytics and report generation screen for Barangay Officials."""
    if request.user.role != 'official':
        messages.error(request, 'Only Barangay Officials can access the Reports / Admin screen.')
        return redirect('staff_dashboard')

    complaints = Complaint.objects.all()
    incidents = Incident.objects.all()

    # Calculate statistics
    total_count = complaints.count() + incidents.count()
    complaints_count = complaints.count()
    incidents_count = incidents.count()
    
    pending_count = complaints.filter(status='Pending').count() + incidents.filter(status='Pending').count()
    in_progress_count = complaints.filter(status='In Progress').count() + incidents.filter(status='In Progress').count()
    resolved_count = complaints.filter(status='Resolved').count() + incidents.filter(status='Resolved').count()

    # Complaints Breakdown
    pending_complaints = complaints.filter(status='Pending').count()
    in_progress_complaints = complaints.filter(status='In Progress').count()
    resolved_complaints = complaints.filter(status='Resolved').count()
    complaint_resolution_rate = int((resolved_complaints / complaints_count * 100)) if complaints_count > 0 else 0

    # Incidents Breakdown
    pending_incidents = incidents.filter(status='Pending').count()
    in_progress_incidents = incidents.filter(status='In Progress').count()
    resolved_incidents = incidents.filter(status='Resolved').count()
    incident_resolution_rate = int((resolved_incidents / incidents_count * 100)) if incidents_count > 0 else 0

    # Overall Resolution Rate
    total_resolution_rate = int((resolved_count / total_count * 100)) if total_count > 0 else 0

    # Category breakdowns (merged)
    categories = {}
    for c in complaints:
        categories[c.category] = categories.get(c.category, 0) + 1
    for i in incidents:
        categories[i.category] = categories.get(i.category, 0) + 1
        
    category_list = [{'name': k, 'count': v} for k, v in categories.items()]

    # Case Trend (Monthly report volumes) over the last 6 months
    import datetime
    from django.utils import timezone
    from collections import OrderedDict

    today = timezone.now().date()
    months_data = OrderedDict()
    
    for i in range(5, -1, -1):
        first_day_current = today.replace(day=1)
        year = first_day_current.year
        month = first_day_current.month - i
        while month <= 0:
            month += 12
            year -= 1
        month_date = datetime.date(year, month, 1)
        month_key = month_date.strftime('%Y-%m')
        month_label = month_date.strftime('%b %Y')
        months_data[month_key] = {
            'label': month_label,
            'total': 0,
            'complaints': 0,
            'incidents': 0
        }

    for c in complaints:
        local_created_at = timezone.localtime(c.date_submitted)
        r_month_key = local_created_at.strftime('%Y-%m')
        if r_month_key in months_data:
            months_data[r_month_key]['total'] += 1
            months_data[r_month_key]['complaints'] += 1

    for i in incidents:
        local_created_at = timezone.localtime(i.date_reported)
        r_month_key = local_created_at.strftime('%Y-%m')
        if r_month_key in months_data:
            months_data[r_month_key]['total'] += 1
            months_data[r_month_key]['incidents'] += 1

    trend_labels = [m['label'] for m in months_data.values()]
    trend_totals = [m['total'] for m in months_data.values()]
    trend_complaints = [m['complaints'] for m in months_data.values()]
    trend_incidents = [m['incidents'] for m in months_data.values()]

    # Registry of concerns table
    reports = []
    for c in complaints:
        evidence_file = c.evidence.first()
        reports.append({
            'id': c.complaint_id,
            'title': c.title,
            'description': c.description,
            'status': c.status,
            'remarks': c.remarks,
            'report_type': 'complaint',
            'created_at': c.date_submitted,
            'resident': c.user,
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
            'resident': i.user,
            'evidence': evidence_file.file_path if evidence_file else None,
            'location': i.location,
            'latitude': i.latitude,
            'longitude': i.longitude,
        })
        
    reports.sort(key=lambda x: x['created_at'], reverse=True)

    context = {
        'user': request.user,
        'reports': reports,
        'total_count': total_count,
        'complaints_count': complaints_count,
        'incidents_count': incidents_count,
        'pending_count': pending_count,
        'in_progress_count': in_progress_count,
        'resolved_count': resolved_count,
        'pending_complaints': pending_complaints,
        'in_progress_complaints': in_progress_complaints,
        'resolved_complaints': resolved_complaints,
        'complaint_resolution_rate': complaint_resolution_rate,
        'pending_incidents': pending_incidents,
        'in_progress_incidents': in_progress_incidents,
        'resolved_incidents': resolved_incidents,
        'incident_resolution_rate': incident_resolution_rate,
        'total_resolution_rate': total_resolution_rate,
        'category_list': category_list,
        'trend_labels': trend_labels,
        'trend_totals': trend_totals,
        'trend_complaints': trend_complaints,
        'trend_incidents': trend_incidents,
    }
    return render(request, 'barangay_app/official_reports.html', context)


@login_required(login_url='login')
def user_management(request):
    """User accounts management console. Only accessible by Barangay Officials."""
    if request.user.role != 'official':
        messages.error(request, 'Only Barangay Officials can access the User Management panel.')
        return redirect('staff_dashboard')

    users = User.objects.all().order_by('-created_at')

    # Summary Statistics
    total_users = users.count()
    residents_count = users.filter(role='resident').count()
    staff_count = users.filter(role='staff').count()
    officials_count = users.filter(role='official').count()

    context = {
        'user': request.user,
        'users': users,
        'total_users': total_users,
        'residents_count': residents_count,
        'staff_count': staff_count,
        'officials_count': officials_count,
    }
    return render(request, 'barangay_app/user_management.html', context)


@login_required(login_url='login')
def add_user(request):
    """Add a new user account. Only accessible by Barangay Officials."""
    if request.user.role != 'official':
        messages.error(request, 'Only Barangay Officials can add users.')
        return redirect('staff_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        contact_number = request.POST.get('contact_number', '').strip()
        role = request.POST.get('role', 'resident')
        status = request.POST.get('status', 'active')
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not username or not email or not password or not first_name or not last_name:
            messages.error(request, 'Please fill in all required fields.')
            return redirect('user_management')

        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('user_management')

        if User.objects.filter(username=username).exists():
            messages.error(request, f"Username '{username}' is already taken.")
            return redirect('user_management')

        if User.objects.filter(email=email).exists():
            messages.error(request, f"An account with the email '{email}' already exists.")
            return redirect('user_management')

        # Create user
        new_user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=role,
            contact_number=contact_number,
            status=status
        )
        
        # If staff or official, set is_staff=True so they can log into admin panels if needed
        if role in ('staff', 'official'):
            new_user.is_staff = True
            new_user.save()

        # Log action
        ActivityLog.objects.create(
            user=request.user,
            action=f"Created user account '{username}' with role '{role}'."
        )

        messages.success(request, f"User account '{username}' successfully created!")

    return redirect('user_management')


@login_required(login_url='login')
def edit_user(request, target_user_id):
    """Edit an existing user account. Only accessible by Barangay Officials."""
    if request.user.role != 'official':
        messages.error(request, 'Only Barangay Officials can edit user profiles.')
        return redirect('staff_dashboard')

    target_user = get_object_or_404(User, user_id=target_user_id)

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        contact_number = request.POST.get('contact_number', '').strip()
        role = request.POST.get('role', target_user.role)
        status = request.POST.get('status', target_user.status)
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        if not email or not first_name or not last_name:
            messages.error(request, 'First name, last name, and email are required.')
            return redirect('user_management')

        if password:
            if password != confirm_password:
                messages.error(request, 'Passwords do not match.')
                return redirect('user_management')

        # Check if email is taken by another user
        if User.objects.filter(email=email).exclude(user_id=target_user_id).exists():
            messages.error(request, f"The email '{email}' is already in use by another account.")
            return redirect('user_management')

        # Update details
        target_user.first_name = first_name
        target_user.last_name = last_name
        target_user.email = email
        target_user.contact_number = contact_number
        target_user.role = role
        target_user.status = status

        if role in ('staff', 'official'):
            target_user.is_staff = True
        else:
            target_user.is_staff = False

        if password:
            target_user.set_password(password)

        target_user.save()

        # Log action
        ActivityLog.objects.create(
            user=request.user,
            action=f"Modified user account details for '{target_user.username}'."
        )

        messages.success(request, f"User account '{target_user.username}' successfully updated!")

    return redirect('user_management')


@login_required(login_url='login')
def test_email_view(request):
    """Quick endpoint for staff/officials to verify Gmail SMTP is working."""
    if not request.user.is_staff_or_official:
        return JsonResponse({'status': 'error', 'message': 'Access denied.'}, status=403)

    recipient = request.user.email
    if not recipient:
        return JsonResponse(
            {'status': 'error', 'message': 'Your account has no email address.'},
            status=400,
        )

    success = send_test_email(recipient)

    if success:
        return JsonResponse({
            'status': 'success',
            'message': f'Test email sent to {recipient}. Check your inbox!',
        })
    else:
        return JsonResponse({
            'status': 'error',
            'message': 'Failed to send test email. Check server logs for details.',
        }, status=500)


@login_required(login_url='login')
def activity_log_view(request):
    """Activity Log for Barangay Staff and Officials."""
    if not request.user.is_staff_or_official:
        messages.error(request, 'Access denied.')
        return redirect('resident_dashboard')

    if request.user.role == 'official':
        logs = ActivityLog.objects.all().select_related('user').order_by('-timestamp')
    else:
        # Staff can only see their own logs
        logs = ActivityLog.objects.filter(user=request.user).select_related('user').order_by('-timestamp')
        
    return render(request, 'barangay_app/activity_log.html', {
        'logs': logs,
    })


@login_required(login_url='login')
def backup_recovery_view(request):
    """Backup & Recovery management dashboard. Only accessible by officials."""
    if request.user.role != 'official':
        messages.error(request, 'Access denied. Only Barangay Officials can access Backup & Recovery.')
        return redirect('staff_dashboard')
        
    # Passively check if we need to run the weekly scheduled backup
    from .backup_utils import check_and_run_weekly_backup, get_backup_settings
    try:
        check_and_run_weekly_backup()
    except Exception:
        # Don't fail the page view if weekly scheduled check fails
        pass

    all_backups = DatabaseBackup.objects.all().select_related('created_by').order_by('-created_at')
    backups = []
    for b in all_backups:
        if os.path.exists(b.file_path):
            backups.append(b)
        else:
            b.delete()
    settings_obj = get_backup_settings()
    
    # Calculate active DB size
    db_config = settings.DATABASES['default']
    active_db_path = db_config['NAME']
    active_db_size = 0
    if os.path.exists(active_db_path):
        active_db_size = os.path.getsize(active_db_path)
        
    context = {
        'user': request.user,
        'backups': backups,
        'active_db_size': active_db_size,
        'backup_settings': settings_obj,
    }
    return render(request, 'barangay_app/backup_recovery.html', context)


@login_required(login_url='login')
def update_backup_settings_view(request):
    """Update scheduled backup configuration."""
    if request.user.role != 'official':
        messages.error(request, 'Access denied.')
        return redirect('staff_dashboard')
        
    if request.method == 'POST':
        auto_backup_enabled = request.POST.get('auto_backup_enabled') == 'on'
        day = request.POST.get('backup_day')
        time_str = request.POST.get('backup_time')
        
        from .backup_utils import get_backup_settings
        settings_obj = get_backup_settings()
        
        try:
            settings_obj.auto_backup_enabled = auto_backup_enabled
            
            if auto_backup_enabled:
                if day and time_str:
                    import datetime
                    time_parts = time_str.split(':')
                    hour = int(time_parts[0])
                    minute = int(time_parts[1])
                    time_obj = datetime.time(hour, minute)
                    
                    settings_obj.backup_day = day
                    settings_obj.backup_time = time_obj
                    msg = f"Automated backups enabled. Schedule set to {day}s at {time_str}."
                else:
                    raise ValueError("Backup day and time are required when automated backups are enabled.")
            else:
                msg = "Automated backups disabled."
                
            settings_obj.save()
            
            # Log action
            ActivityLog.objects.create(
                user=request.user,
                action=f"Updated backup settings: {msg}"
            )
            messages.success(request, msg)
        except Exception as e:
            messages.error(request, f"Failed to update backup schedule: {str(e)}")
            
    return redirect('backup_recovery')


@login_required(login_url='login')
def create_backup_view(request):
    """Create a manual database backup."""
    if request.user.role != 'official':
        messages.error(request, 'Access denied.')
        return redirect('staff_dashboard')
        
    if request.method == 'POST':
        from .backup_utils import perform_db_backup
        backup, error = perform_db_backup(user=request.user, backup_type='manual')
        if error:
            messages.error(request, f'Failed to create backup: {error}')
        else:
            messages.success(request, f'Successfully created database backup: {backup.filename}')
            
    return redirect('backup_recovery')


@login_required(login_url='login')
def download_backup_view(request, backup_id):
    """Download a database backup file."""
    if request.user.role != 'official':
        messages.error(request, 'Access denied.')
        return redirect('staff_dashboard')
        
    backup = get_object_or_404(DatabaseBackup, backup_id=backup_id)
    if not os.path.exists(backup.file_path):
        raise Http404("Backup file not found on disk.")
        
    response = FileResponse(open(backup.file_path, 'rb'), content_type='application/x-sqlite3')
    response['Content-Disposition'] = f'attachment; filename="{backup.filename}"'
    return response


@login_required(login_url='login')
def restore_backup_view(request, backup_id):
    """Restore database from a backup."""
    if request.user.role != 'official':
        messages.error(request, 'Access denied.')
        return redirect('staff_dashboard')
        
    if request.method == 'POST':
        backup = get_object_or_404(DatabaseBackup, backup_id=backup_id)
        
        # Save current session to preserve login status
        session_key = request.session.session_key
        session_record = None
        if session_key:
            try:
                from django.contrib.sessions.models import Session
                session_record = Session.objects.get(session_key=session_key)
            except Exception:
                pass

        try:
            from .backup_utils import restore_db_backup
            restore_db_backup(backup, request.user)
            # Programmatically migrate to ensure the restored DB schema matches the current codebase
            from django.core.management import call_command
            call_command('migrate', interactive=False)
            
            # Re-save the session record in the restored database
            if session_record:
                try:
                    session_record.save()
                except Exception:
                    pass
                    
            messages.success(request, f'Database successfully restored to backup: {backup.filename} and schema was updated.')
        except FileNotFoundError as e:
            # Delete stale record from database registry since the file is missing from disk
            backup.delete()
            messages.error(request, f'Restore failed: The backup file was not found on disk. The stale registry record has been cleaned up.')
        except Exception as e:
            messages.error(request, f'Failed to restore database: {str(e)}')
            
    return redirect('backup_recovery')


@login_required(login_url='login')
def delete_backup_view(request, backup_id):
    """Delete a database backup file and record."""
    if request.user.role != 'official':
        messages.error(request, 'Access denied.')
        return redirect('staff_dashboard')
        
    if request.method == 'POST':
        backup = get_object_or_404(DatabaseBackup, backup_id=backup_id)
        filename = backup.filename
        
        # Delete file from disk if it exists
        if os.path.exists(backup.file_path):
            try:
                os.remove(backup.file_path)
            except Exception as e:
                messages.warning(request, f"Backup record deleted, but failed to delete file from disk: {str(e)}")
        
        # Delete record
        backup.delete()
        
        # Log action
        ActivityLog.objects.create(
            user=request.user,
            action=f"Deleted database backup record: {filename}"
        )
        
        messages.success(request, f'Backup {filename} deleted successfully.')
        
    return redirect('backup_recovery')


@login_required(login_url='login')
def upload_backup_view(request):
    """Upload an external database file and immediately restore it, without registering it in the backup registry."""
    if request.user.role != 'official':
        messages.error(request, 'Access denied.')
        return redirect('staff_dashboard')
        
    if request.method == 'POST' and request.FILES.get('backup_file'):
        backup_file = request.FILES['backup_file']
        
        # Validate file extension
        ext = os.path.splitext(backup_file.name)[1].lower()
        if ext not in ['.sqlite3', '.db', '.sqlite']:
            messages.error(request, 'Invalid file type. Only .sqlite3, .db, or .sqlite files are allowed.')
            return redirect('backup_recovery')
            
        # Get active database path
        db_config = settings.DATABASES['default']
        active_db_path = db_config['NAME']
        
        # Save current session to preserve login status
        session_key = request.session.session_key
        session_record = None
        if session_key:
            try:
                from django.contrib.sessions.models import Session
                session_record = Session.objects.get(session_key=session_key)
            except Exception:
                pass
                
        import tempfile
        import shutil
        from django.db import connections
        
        temp_file_fd, temp_file_path = tempfile.mkstemp(suffix=ext)
        try:
            with os.fdopen(temp_file_fd, 'wb') as tmp:
                for chunk in backup_file.chunks():
                    tmp.write(chunk)
            
            # 1. Close all active database connections to avoid file lock issues
            connections.close_all()
            
            # 2. Copy uploaded file over active database
            shutil.copy2(temp_file_path, active_db_path)
            
            # Programmatically migrate to ensure the restored DB schema matches the current codebase
            from django.core.management import call_command
            call_command('migrate', interactive=False)
            
            # Re-save the session record in the restored database
            if session_record:
                try:
                    session_record.save()
                except Exception:
                    pass
                    
            # 3. Create activity log inside the newly restored database
            ActivityLog.objects.create(
                user=request.user,
                action=f"Restored database directly from uploaded file: {backup_file.name}"
            )
            
            messages.success(request, f'Database successfully restored to the uploaded file: {backup_file.name}.')
        except Exception as e:
            messages.error(request, f'Failed to restore database from uploaded file: {str(e)}')
        finally:
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception:
                    pass
            
    return redirect('backup_recovery')


@login_required(login_url='login')
def edit_report(request, report_type, report_id):
    """Edit report details (complaint or incident). Available to officials or assigned staff."""
    if not request.user.is_staff_or_official:
        messages.error(request, 'Access denied.')
        return redirect('resident_dashboard')

    if report_type == 'complaint':
        report = get_object_or_404(Complaint, complaint_id=report_id)
        is_assigned = CaseAssignment.objects.filter(case_type='complaint', case_id=report_id, assigned_to=request.user).exists()
    elif report_type == 'incident':
        report = get_object_or_404(Incident, incident_id=report_id)
        is_assigned = CaseAssignment.objects.filter(case_type='incident', case_id=report_id, assigned_to=request.user).exists()
    else:
        messages.error(request, 'Invalid report type.')
        return redirect('staff_dashboard')

    if request.user.role != 'official' and not is_assigned:
        messages.error(request, 'You can only edit reports assigned to you.')
        return redirect('staff_dashboard')

    if request.method == 'POST':
        category = request.POST.get('category', '').strip()
        description = request.POST.get('description', '').strip()
        status = request.POST.get('status')
        remarks = request.POST.get('remarks', '').strip()
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')

        if report_type == 'complaint':
            title = request.POST.get('title', '').strip()
            if not title:
                messages.error(request, 'Title is required.')
                return redirect('staff_dashboard')
            report.title = title
        else:
            location = request.POST.get('location', '').strip()
            if not location:
                messages.error(request, 'Location description is required.')
                return redirect('staff_dashboard')
            report.location = location

        if not category or not description:
            messages.error(request, 'Category and description are required.')
            return redirect('staff_dashboard')

        report.category = category
        report.description = description
        report.status = status
        report.remarks = remarks
        report.latitude = float(latitude) if latitude else None
        report.longitude = float(longitude) if longitude else None
        report.save()

        # Update status of assignment if assignment exists
        assignment = CaseAssignment.objects.filter(case_type=report_type, case_id=report_id).first()
        if assignment:
            assignment.status = status
            assignment.save()

        # If user is official, allow reassigning staff in the same form
        if request.user.role == 'official':
            staff_id = request.POST.get('staff_id')
            if staff_id:
                try:
                    staff_user = User.objects.get(user_id=staff_id, role='staff')
                    CaseAssignment.objects.update_or_create(
                        case_type=report_type,
                        case_id=report_id,
                        defaults={
                            'assigned_to': staff_user,
                            'assigned_by': request.user,
                            'status': status
                        }
                    )
                except User.DoesNotExist:
                    pass
            else:
                # Unassign
                CaseAssignment.objects.filter(case_type=report_type, case_id=report_id).delete()

        # Fetch final assigned staff details for notification
        assigned_staff_name = "Unassigned"
        final_assignment = CaseAssignment.objects.filter(case_type=report_type, case_id=report_id).first()
        if final_assignment and final_assignment.assigned_to:
            assigned_staff_name = final_assignment.assigned_to.get_full_name() or final_assignment.assigned_to.username

        # Notify resident
        Notification.objects.create(
            user=report.user,
            message=f"The details of your {report_type} (ID: #{report_id}) have been updated by {request.user.get_full_name() or request.user.username} ({request.user.get_role_display()}). Assigned Staff: {assigned_staff_name}."
        )
        send_report_updated_email(report, report_type, request.user)

        # Log action
        ActivityLog.objects.create(
            user=request.user,
            action=f"Edited {report_type} report details: ID #{report_id}"
        )
        messages.success(request, f"{report_type.capitalize()} report details updated successfully.")

    return redirect('staff_dashboard')


@login_required(login_url='login')
def delete_report(request, report_type, report_id):
    """Delete a report. Only officials are authorized."""
    if request.user.role != 'official':
        messages.error(request, 'Only Barangay Officials can delete reports.')
        return redirect('staff_dashboard')

    if request.method == 'POST':
        if report_type == 'complaint':
            report = get_object_or_404(Complaint, complaint_id=report_id)
            title = report.title
        elif report_type == 'incident':
            report = get_object_or_404(Incident, incident_id=report_id)
            title = f"Incident: {report.category}"
        else:
            messages.error(request, 'Invalid report type.')
            return redirect('staff_dashboard')

        # Clean assignments manually as generic case_id is not database cascading
        CaseAssignment.objects.filter(case_type=report_type, case_id=report_id).delete()
        report.delete()

        # Log action
        ActivityLog.objects.create(
            user=request.user,
            action=f"Deleted {report_type} report: '{title}' (ID: #{report_id})"
        )
        messages.success(request, f"{report_type.capitalize()} report #{report_id} has been permanently deleted.")

    return redirect('staff_dashboard')
