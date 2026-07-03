"""
email_utils.py — Reusable email notification helpers for Barangay Connect.

All functions use Django's render_to_string() to send themed HTML emails
and are wrapped in try/except so that a failed email NEVER crashes the application.
"""

import logging
import threading
import requests
from django.template.loader import render_to_string
from django.conf import settings
from django.core.mail import EmailMessage
from django.contrib.auth import get_user_model
from decouple import config

logger = logging.getLogger(__name__)
User = get_user_model()


def _send_email_thread(email, to_emails):
    try:
        email.send(fail_silently=False)
        logger.info(f'Themed HTML email sent via SMTP to {to_emails}.')
    except Exception as e:
        logger.error(f'Failed to send themed HTML email to {to_emails}: {e}')


def _send_email_thread_http(to_emails, subject, html_content, api_key, from_email):
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "from": from_email,
            "to": to_emails,
            "subject": subject,
            "html": html_content,
        }
        response = requests.post("https://api.resend.com/emails", json=data, headers=headers, timeout=15)
        if response.status_code in [200, 201]:
            logger.info(f'Themed HTML email sent via Resend HTTPS API to {to_emails}.')
        else:
            logger.error(f'Failed to send themed HTML email via Resend API to {to_emails}: Status {response.status_code}, {response.text}')
    except Exception as e:
        logger.error(f'Resend HTTPS API Exception for {to_emails}: {e}')


def send_themed_email(to_emails, subject, recipient_name, message_body, details=None):
    """Sends a themed HTML email using email/notification.html.

    Args:
        to_emails (str or list): One or more email addresses.
        subject (str): Email subject.
        recipient_name (str): Name of recipient(s) to address.
        message_body (str): Content of the email.
        details (list of tuple, optional): Key-value pairs to display in a structured table.
    """
    if isinstance(to_emails, str):
        to_emails = [to_emails]

    try:
        context = {
            'subject': subject,
            'recipient_name': recipient_name,
            'message_body': message_body,
            'details': details,
        }
        html_content = render_to_string('email/notification.html', context)
        
        # Check if Resend API Key is set to bypass blocked SMTP ports on Render/DigitalOcean
        resend_api_key = config('RESEND_API_KEY', default='')
        if resend_api_key:
            threading.Thread(
                target=_send_email_thread_http,
                args=(to_emails, subject, html_content, resend_api_key, settings.DEFAULT_FROM_EMAIL),
                daemon=True
            ).start()
            return True

        # Fallback to standard Django SMTP
        email = EmailMessage(
            subject=subject,
            body=html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=to_emails,
        )
        email.content_subtype = 'html'
        
        # Send asynchronously to prevent blocking Gunicorn workers
        threading.Thread(target=_send_email_thread, args=(email, to_emails), daemon=True).start()
        return True
    except Exception as e:
        logger.error(f'Failed to initialize themed HTML email to {to_emails}: {e}')
        return False






def send_resident_notification(to_email, subject, template_name, context):
    """Render an HTML email template and send it to a resident.
    Maintained for backward compatibility.
    """
    return send_themed_email(
        to_emails=to_email,
        subject=subject,
        recipient_name=context.get('recipient_name', 'Resident'),
        message_body=context.get('message_body', ''),
        details=context.get('details', None)
    )


def send_report_submitted_email(case_obj, case_type):
    if case_type == 'complaint':
        subject = f'[Barangay Connect] New Complaint Filed: {case_obj.title}'
        message_body = 'A new complaint has been submitted. Please review the details below:'
        details = [
            ('Case Type', 'Complaint'),
            ('Title', case_obj.title),
            ('Category', case_obj.category),
            ('Description', case_obj.description),
            ('Submitted by', case_obj.user.get_full_name() or case_obj.user.username),
            ('Date Submitted', case_obj.date_submitted.strftime('%Y-%m-%d %H:%M')),
        ]
    else:
        subject = f'[Barangay Connect] New Incident Reported: {case_obj.category}'
        message_body = 'A new incident has been reported. Please review the details below:'
        details = [
            ('Case Type', 'Incident'),
            ('Category', case_obj.category),
            ('Location', case_obj.location),
            ('Description', case_obj.description),
            ('Reported by', case_obj.user.get_full_name() or case_obj.user.username),
            ('Date Reported', case_obj.date_reported.strftime('%Y-%m-%d %H:%M')),
        ]

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
        message_body=message_body,
        details=details
    )


def send_status_update_email(case_obj, case_type, new_status, updater_user=None):
    resident = case_obj.user

    if not resident.email:
        logger.warning(f'Resident {resident.username} has no email — skipping notification.')
        return

    if case_type == 'complaint':
        case_label = f'Complaint #{case_obj.complaint_id}: {case_obj.title}'
    else:
        case_label = f'Incident #{case_obj.incident_id}: {case_obj.category} at {case_obj.location}'

    subject = f'[Barangay Connect] Your {case_type.title()} Status Updated to "{new_status}"'
    message_body = f'The status of your {case_type} has been updated. Please see details below:'

    details = [
        ('Case', case_label),
        ('New Status', new_status),
    ]
    if updater_user:
        details.append(('Updated By', f'{updater_user.get_full_name() or updater_user.username} ({updater_user.get_role_display()})'))

    send_themed_email(
        to_emails=resident.email,
        subject=subject,
        recipient_name=resident.get_full_name() or resident.username,
        message_body=message_body,
        details=details
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
        message_body = f'You have been assigned to investigate the following {case_type}:'
        details = [
            ('Case', case_label),
            ('Description', case_obj.description),
            ('Assigned by', f'{assigned_by.get_full_name() or assigned_by.username} ({assigned_by.get_role_display()})'),
        ]
        send_themed_email(
            to_emails=staff_user.email,
            subject=subject,
            recipient_name=staff_user.get_full_name() or staff_user.username,
            message_body=message_body,
            details=details
        )

    # ── Email to resident ───────────────────────────────────
    if resident.email:
        subject = f'[Barangay Connect] Your {case_type.title()} Has Been Assigned'
        message_body = f'Your {case_type} is now being handled. A staff member has been assigned to investigate.'
        details = [
            ('Case', case_label),
            ('Assigned to', f'{staff_user.get_full_name() or staff_user.username} ({staff_user.get_role_display()})'),
            ('Assigned by', f'{assigned_by.get_full_name() or assigned_by.username} ({assigned_by.get_role_display()})'),
        ]
        send_themed_email(
            to_emails=resident.email,
            subject=subject,
            recipient_name=resident.get_full_name() or resident.username,
            message_body=message_body,
            details=details
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


def send_report_updated_email(case_obj, case_type, updater_user, changes=None):
    resident = case_obj.user
    if not resident.email:
        logger.warning(f'Resident {resident.username} has no email — skipping notification.')
        return

    if case_type == 'complaint':
        case_label = f'Complaint #{case_obj.complaint_id}: {case_obj.title}'
    else:
        case_label = f'Incident #{case_obj.incident_id}: {case_obj.category} at {case_obj.location}'

    updater_name = f"{updater_user.get_full_name() or updater_user.username} ({updater_user.get_role_display()})" if updater_user else "A staff member or official"
    subject = f'[Barangay Connect] Your {case_type.title()} Details Have Been Updated'
    message_body = f'{updater_name} has updated the details of your {case_type}. Please see the details of the update below:'

    from resident.models import CaseAssignment
    assignment = CaseAssignment.objects.filter(case_type=case_type, case_id=case_obj.pk).first()
    assigned_staff = f"{assignment.assigned_to.get_full_name() or assignment.assigned_to.username}" if assignment and assignment.assigned_to else "Unassigned"

    details = [
        ('Case', case_label),
    ]

    if changes:
        changes_str = "\n".join([f"• {change}" for change in changes])
        details.append(('Changes Made', changes_str))

    details.extend([
        ('Category', case_obj.category),
        ('Description', case_obj.description),
        ('Status', case_obj.status),
        ('Assigned Staff', assigned_staff),
    ])

    if case_type == 'incident':
        details.append(('Location', case_obj.location))
    if case_obj.remarks:
        details.append(('Remarks', case_obj.remarks))
    if updater_user:
        details.append(('Updated By', f'{updater_user.get_full_name() or updater_user.username} ({updater_user.get_role_display()})'))

    send_themed_email(
        to_emails=resident.email,
        subject=subject,
        recipient_name=resident.get_full_name() or resident.username,
        message_body=message_body,
        details=details
    )
