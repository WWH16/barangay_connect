"""
email_utils.py — Reusable email notification helpers for Barangay Connect.

All functions use Django's send_mail() and are wrapped in try/except
so that a failed email NEVER crashes the application.

Usage:
    from barangay_app.email_utils import send_report_submitted_email
    send_report_submitted_email(complaint_obj, request.user)
"""

import logging
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()

def send_report_submitted_email(case_obj, case_type):
    if case_type == 'complaint':
        subject = f'[Barangay Connect] New Complaint Filed: {case_obj.title}'
        body = (
            f'A new complaint has been submitted.\n\n'
            f'Title: {case_obj.title}\n'
            f'Category: {case_obj.category}\n'
            f'Description: {case_obj.description}\n'
            f'Submitted by: {case_obj.user.get_full_name() or case_obj.user.username}\n'
            f'Date: {case_obj.date_submitted}\n\n'
            f'Please log in to Barangay Connect to review and take action.'
        )
    else:
        subject = f'[Barangay Connect] New Incident Reported: {case_obj.category}'
        body = (
            f'A new incident has been reported.\n\n'
            f'Category: {case_obj.category}\n'
            f'Location: {case_obj.location}\n'
            f'Description: {case_obj.description}\n'
            f'Reported by: {case_obj.user.get_full_name() or case_obj.user.username}\n'
            f'Date: {case_obj.date_reported}\n\n'
            f'Please log in to Barangay Connect to review and take action.'
        )

    # Gather email addresses of all staff and officials
    staff_emails = list(
        User.objects.filter(
            role__in=['staff', 'official'],
            status='active',
        )
        .exclude(email='')
        .values_list('email', flat=True)
    )

    if not staff_emails:
        logger.warning('No staff/official email addresses found — skipping notification.')
        return

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=staff_emails,
            fail_silently=False,
        )
        logger.info(f'Report-submitted email sent to {len(staff_emails)} recipient(s).')
    except Exception as e:
        logger.error(f'Failed to send report-submitted email: {e}')

def send_status_update_email(case_obj, case_type, new_status):
    resident = case_obj.user

    if not resident.email:
        logger.warning(f'Resident {resident.username} has no email — skipping notification.')
        return

    if case_type == 'complaint':
        case_label = f'Complaint #{case_obj.complaint_id}: {case_obj.title}'
    else:
        case_label = f'Incident #{case_obj.incident_id}: {case_obj.category} at {case_obj.location}'

    subject = f'[Barangay Connect] Your {case_type.title()} Status Updated to "{new_status}"'
    body = (
        f'Good day, {resident.get_full_name() or resident.username}!\n\n'
        f'Your {case_type} has been updated:\n\n'
        f'Case: {case_label}\n'
        f'New Status: {new_status}\n\n'
        f'Log in to Barangay Connect for more details.\n\n'
        f'Thank you,\n'
        f'Barangay Connect Team'
    )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[resident.email],
            fail_silently=False,
        )
        logger.info(f'Status-update email sent to {resident.email}.')
    except Exception as e:
        logger.error(f'Failed to send status-update email to {resident.email}: {e}')

def send_case_assigned_email(case_obj, case_type, staff_user, assigned_by):
    resident = case_obj.user

    if case_type == 'complaint':
        case_label = f'Complaint #{case_obj.complaint_id}: {case_obj.title}'
    else:
        case_label = f'Incident #{case_obj.incident_id}: {case_obj.category} at {case_obj.location}'

    # ── Email to staff ──────────────────────────────────────
    if staff_user.email:
        try:
            send_mail(
                subject=f'[Barangay Connect] You have been assigned: {case_label}',
                message=(
                    f'Hi {staff_user.get_full_name() or staff_user.username},\n\n'
                    f'You have been assigned to investigate the following {case_type}:\n\n'
                    f'Case: {case_label}\n'
                    f'Description: {case_obj.description}\n'
                    f'Assigned by: {assigned_by.get_full_name() or assigned_by.username}\n\n'
                    f'Please log in to Barangay Connect to take action.\n\n'
                    f'Thank you,\n'
                    f'Barangay Connect Team'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[staff_user.email],
                fail_silently=False,
            )
            logger.info(f'Assignment email sent to staff {staff_user.email}.')
        except Exception as e:
            logger.error(f'Failed to send assignment email to staff {staff_user.email}: {e}')

    # ── Email to resident ───────────────────────────────────
    if resident.email:
        try:
            send_mail(
                subject=f'[Barangay Connect] Your {case_type.title()} Has Been Assigned',
                message=(
                    f'Good day, {resident.get_full_name() or resident.username}!\n\n'
                    f'Your {case_type} is now being handled:\n\n'
                    f'Case: {case_label}\n'
                    f'Assigned to: {staff_user.get_full_name() or staff_user.username}\n\n'
                    f'You will receive further updates as your case progresses.\n\n'
                    f'Thank you,\n'
                    f'Barangay Connect Team'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[resident.email],
                fail_silently=False,
            )
            logger.info(f'Assignment notification email sent to resident {resident.email}.')
        except Exception as e:
            logger.error(f'Failed to send assignment email to resident {resident.email}: {e}')

def send_test_email(recipient_email):
    try:
        send_mail(
            subject='[Barangay Connect] SMTP Test — Success!',
            message=(
                'If you are reading this, your Gmail SMTP configuration '
                'is working correctly.\n\n'
                '— Barangay Connect'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        logger.info(f'Test email sent successfully to {recipient_email}.')
        return True
    except Exception as e:
        logger.error(f'Test email failed: {e}')
        return False
