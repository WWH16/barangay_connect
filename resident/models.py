from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    """Custom user model mapping to table 'User'."""
    ROLE_CHOICES = (
        ('resident', 'Resident'),
        ('staff', 'Barangay Staff'),
        ('official', 'Barangay Official'),
    )
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    )
    
    user_id = models.AutoField(primary_key=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='resident')
    contact_number = models.CharField(max_length=20, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'User'

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_resident(self):
        return self.role == 'resident'

    @property
    def is_official(self):
        return self.role == 'official'

    @property
    def is_staff_or_official(self):
        return self.role in ('staff', 'official')


class Complaint(models.Model):
    """Complaint submitted by a resident."""
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Resolved', 'Resolved'),
    )
    complaint_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id', related_name='complaints')
    category = models.CharField(max_length=100)
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    remarks = models.TextField(blank=True, default='')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    date_submitted = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'Complaint'
        ordering = ['-date_submitted']

    def __str__(self):
        return f"Complaint #{self.complaint_id}: {self.title}"


class Incident(models.Model):
    """Incident report submitted by a resident."""
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Resolved', 'Resolved'),
    )
    incident_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id', related_name='incidents')
    category = models.CharField(max_length=100)
    location = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    remarks = models.TextField(blank=True, default='')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    date_reported = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'Incident'
        ordering = ['-date_reported']

    def __str__(self):
        return f"Incident #{self.incident_id}: {self.category} at {self.location}"


class EvidenceFile(models.Model):
    """Evidence file or attachment associated with a complaint or incident."""
    file_id = models.AutoField(primary_key=True)
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, null=True, blank=True, db_column='complaint_id', related_name='evidence')
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, null=True, blank=True, db_column='incident_id', related_name='evidence')
    file_path = models.FileField(upload_to='evidence/')
    file_type = models.CharField(max_length=50)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'EvidenceFile'

    def __str__(self):
        return f"Evidence File #{self.file_id} ({self.file_type})"


class CaseAssignment(models.Model):
    """Assignment of a case (complaint/incident) to a staff member."""
    CASE_TYPE_CHOICES = (
        ('complaint', 'Complaint'),
        ('incident', 'Incident'),
    )
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Resolved', 'Resolved'),
    )
    assignment_id = models.AutoField(primary_key=True)
    case_type = models.CharField(max_length=20, choices=CASE_TYPE_CHOICES)
    case_id = models.IntegerField()
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, db_column='assigned_to', related_name='assigned_cases')
    assigned_by = models.ForeignKey(User, on_delete=models.CASCADE, db_column='assigned_by', related_name='assigned_by_cases')
    assigned_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')

    class Meta:
        db_table = 'CaseAssignment'

    def __str__(self):
        return f"Assignment #{self.assignment_id}: {self.case_type} #{self.case_id} to {self.assigned_to.username}"


class Notification(models.Model):
    """System notification for a user."""
    notification_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id', related_name='notifications')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'Notification'
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification #{self.notification_id} for {self.user.username}"


class ActivityLog(models.Model):
    """Activity log for auditing actions."""
    log_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id', related_name='activity_logs')
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ActivityLog'
        ordering = ['-timestamp']

    def __str__(self):
        return f"ActivityLog #{self.log_id}: {self.user.username} - {self.action}"
