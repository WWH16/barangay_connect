"""
email_utils.py — Reusable email notification helpers for Barangay Connect.

All functions use Django's render_to_string() to send themed HTML emails
and are wrapped in try/except so that a failed email NEVER crashes the application.
"""

import logging
from django.template.loader import render_to_string
from django.conf import settings
from django.core.mail import EmailMessage
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


def send_themed_email(to_emails, subject, recipient_name, message_body):
    """Sends a themed HTML email using email/notification.html.

    Args:
        to_emails (str or list): One or more email addresses.
        subject (str): Email subject.
        recipient_name (str): Name of recipient(s) to address.
        message_body (str): Content of the email.
    """
    if isinstance(to_emails, str):
        to_emails = [to_emails]

    try:
        context = {
            'subject': subject,
            'recipient_name': recipient_name,
            'message_body': message_body,
        }
        html_content = render_to_string('email/notification.html', context)
        email = EmailMessage(
            subject=subject,
            body=html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=to_emails,
        )
        email.content_subtype = 'html'
        email.send(fail_silently=False)
        logger.info(f'Themed HTML email sent to {to_emails}.')
        return True
    except Exception as e:
        logger.error(f'Failed to send themed HTML email to {to_emails}: {e}')
        return False


def send_resident_notification(to_email, subject, template_name, context):
    """Render an HTML email template and send it to a resident.
    Maintained for backward compatibility.
    """
    return send_themed_email(
        to_emails=to_email,
        subject=subject,
        recipient_name=context.get('recipient_name', 'Resident'),
        message_body=context.get('message_body', '')
    )


def send_report_submitted_email(case_obj, case_type):
    if case_type == 'complaint':
        subject = f'[Barangay Connect] New Complaint Filed: {case_obj.title}'
        message_body = (
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
        message_body = (
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

    send_themed_email(
        to_emails=staff_emails,
        subject=subject,
        recipient_name='Staff / Official',
        message_body=message_body
    )


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
    message_body = (
        f'Your {case_type} status has been updated:\n\n'
        f'Case: {case_label}\n'
        f'New Status: {new_status}\n\n'
        f'Log in to Barangay Connect for more details.'
    )

    send_themed_email(
        to_emails=resident.email,
        subject=subject,
        recipient_name=resident.get_full_name() or resident.username,
        message_body=message_body
    )


def send_case_assigned_email(case_obj, case_type, staff_user, assigned_by):
    resident = case_obj.user

    if case_type == 'complaint':
        case_label = f'Complaint #{case_obj.complaint_id}: {case_obj.title}'
    else:
        case_label = f'Incident #{case_obj.incident_id}: {case_obj.category} at {case_obj.location}'

    # ── Email to staff ──────────────────────────────────────
    if staff_user.email:
        subject = f'[Barangay Connect] You have been assigned: {case_label}'
        message_body = (
            f'You have been assigned to investigate the following {case_type}:\n\n'
            f'Case: {case_label}\n'
            f'Description: {case_obj.description}\n'
            f'Assigned by: {assigned_by.get_full_name() or assigned_by.username}\n\n'
            f'Please log in to Barangay Connect to take action.'
        )
        send_themed_email(
            to_emails=staff_user.email,
            subject=subject,
            recipient_name=staff_user.get_full_name() or staff_user.username,
            message_body=message_body
        )

    # ── Email to resident ───────────────────────────────────
    if resident.email:
        subject = f'[Barangay Connect] Your {case_type.title()} Has Been Assigned'
        message_body = (
            f'Your {case_type} is now being handled:\n\n'
            f'Case: {case_label}\n'
            f'Assigned to: {staff_user.get_full_name() or staff_user.username}\n\n'
            f'You will receive further updates as your case progresses.'
        )
        send_themed_email(
            to_emails=resident.email,
            subject=subject,
            recipient_name=resident.get_full_name() or resident.username,
            message_body=message_body
        )


def send_test_email(recipient_email):
    subject = '[Barangay Connect] SMTP Test — Success!'
    message_body = (
        'If you are reading this, your Gmail SMTP configuration '
        'is working correctly.'
    )
    return send_themed_email(
        to_emails=recipient_email,
        subject=subject,
        recipient_name='Resident / Staff',
        message_body=message_body
    )
