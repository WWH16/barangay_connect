from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from resident.models import Profile, Report


@login_required(login_url='login')
def staff_dashboard(request):
    """Dashboard for barangay staff and officials — shows all reports from residents."""
    profile, _ = Profile.objects.get_or_create(user=request.user, defaults={'role': 'resident'})

    if profile.is_resident:
        return redirect('resident_dashboard')

    if profile.is_official:
        reports = Report.objects.all()
    else:
        reports = Report.objects.filter(assigned_to=request.user)

    # Get all staff members for the assignment dropdown
    staff_members = User.objects.filter(profile__role='staff')

    context = {
        'user': request.user,
        'profile': profile,
        'reports': reports,
        'staff_members': staff_members,
        'total_reports': reports.count(),
        'pending_count': reports.filter(status='Pending').count(),
        'in_progress_count': reports.filter(status='In Progress').count(),
        'resolved_count': reports.filter(status='Resolved').count(),
    }
    return render(request, 'barangay_app/dashboard.html', context)


@login_required(login_url='login')
def assign_report(request, report_id):
    """Assign a report to a staff member. Only officials can assign."""
    profile, _ = Profile.objects.get_or_create(user=request.user, defaults={'role': 'resident'})
    if not profile.is_official:
        messages.error(request, 'Only Barangay Officials can assign reports.')
        return redirect('staff_dashboard')

    if request.method == 'POST':
        report = get_object_or_404(Report, id=report_id)
        staff_id = request.POST.get('staff_id')
        if staff_id:
            try:
                staff_user = User.objects.get(id=staff_id, profile__role='staff')
                report.assigned_to = staff_user
                if report.status == 'Pending':
                    report.status = 'In Progress'
                report.save()
                messages.success(request, f'Report assigned to {staff_user.get_full_name() or staff_user.username}.')
            except User.DoesNotExist:
                messages.error(request, 'Selected staff member not found.')
        else:
            report.assigned_to = None
            report.save()
            messages.success(request, 'Report unassigned.')

    return redirect('staff_dashboard')


@login_required(login_url='login')
def update_report_status(request, report_id):
    """Update report status. Staff can only update reports assigned to them or if they are officials."""
    profile, _ = Profile.objects.get_or_create(user=request.user, defaults={'role': 'resident'})
    if not profile.is_staff_or_official:
        messages.error(request, 'Access denied.')
        return redirect('resident_dashboard')

    if request.method == 'POST':
        report = get_object_or_404(Report, id=report_id)
        # Security check: if staff (but not official), must be assigned to them
        if profile.is_staff and report.assigned_to != request.user:
            messages.error(request, 'You can only update reports assigned to you.')
            return redirect('staff_dashboard')

        new_status = request.POST.get('status')
        if new_status in ['Pending', 'In Progress', 'Resolved']:
            report.status = new_status
            report.save()
            messages.success(request, f'Report status updated to {new_status}.')
        else:
            messages.error(request, 'Invalid status choice.')

    return redirect('staff_dashboard')


@login_required(login_url='login')
def update_report_remarks(request, report_id):
    """Update report remarks, updates, or decisions. Staff can only update reports assigned to them or if they are officials."""
    profile, _ = Profile.objects.get_or_create(user=request.user, defaults={'role': 'resident'})
    if not profile.is_staff_or_official:
        messages.error(request, 'Access denied.')
        return redirect('resident_dashboard')

    if request.method == 'POST':
        report = get_object_or_404(Report, id=report_id)
        # Security check: if staff (but not official), must be assigned to them
        if profile.is_staff and report.assigned_to != request.user:
            messages.error(request, 'You can only update reports assigned to you.')
            return redirect('staff_dashboard')

        new_remarks = request.POST.get('remarks', '').strip()
        report.remarks = new_remarks
        report.save()
        messages.success(request, 'Report remarks updated successfully.')

    return redirect('staff_dashboard')


@login_required(login_url='login')

def official_reports(request):
    """Analytics and report generation screen for Barangay Officials."""
    profile, _ = Profile.objects.get_or_create(user=request.user, defaults={'role': 'resident'})
    if not profile.is_official:
        messages.error(request, 'Only Barangay Officials can access the Reports / Admin screen.')
        return redirect('staff_dashboard')

    reports = Report.objects.all()

    # Calculate statistics
    total_count = reports.count()
    complaints_count = reports.filter(report_type='complaint').count()
    incidents_count = reports.filter(report_type='incident').count()
    
    pending_count = reports.filter(status='Pending').count()
    in_progress_count = reports.filter(status='In Progress').count()
    resolved_count = reports.filter(status='Resolved').count()

    # Complaints Breakdown
    pending_complaints = reports.filter(report_type='complaint', status='Pending').count()
    in_progress_complaints = reports.filter(report_type='complaint', status='In Progress').count()
    resolved_complaints = reports.filter(report_type='complaint', status='Resolved').count()
    complaint_resolution_rate = int((resolved_complaints / complaints_count * 100)) if complaints_count > 0 else 0

    # Incidents Breakdown
    pending_incidents = reports.filter(report_type='incident', status='Pending').count()
    in_progress_incidents = reports.filter(report_type='incident', status='In Progress').count()
    resolved_incidents = reports.filter(report_type='incident', status='Resolved').count()
    incident_resolution_rate = int((resolved_incidents / incidents_count * 100)) if incidents_count > 0 else 0

    # Overall Resolution Rate
    total_resolution_rate = int((resolved_count / total_count * 100)) if total_count > 0 else 0

    # Category breakdowns
    categories = {}
    for r in reports:
        categories[r.category] = categories.get(r.category, 0) + 1
        
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

    for r in reports:
        local_created_at = timezone.localtime(r.created_at)
        r_month_key = local_created_at.strftime('%Y-%m')
        if r_month_key in months_data:
            months_data[r_month_key]['total'] += 1
            if r.report_type == 'complaint':
                months_data[r_month_key]['complaints'] += 1
            elif r.report_type == 'incident':
                months_data[r_month_key]['incidents'] += 1

    trend_labels = [m['label'] for m in months_data.values()]
    trend_totals = [m['total'] for m in months_data.values()]
    trend_complaints = [m['complaints'] for m in months_data.values()]
    trend_incidents = [m['incidents'] for m in months_data.values()]

    context = {
        'user': request.user,
        'profile': profile,
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

