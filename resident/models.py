from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    """Extended user profile with role-based access."""
    ROLE_CHOICES = (
        ('resident', 'Resident'),
        ('staff', 'Barangay Staff'),
        ('official', 'Barangay Official'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='resident')
    contact_number = models.CharField(max_length=20, blank=True, default='')

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

    @property
    def is_resident(self):
        return self.role == 'resident'

    @property
    def is_official(self):
        return self.role == 'official'

    @property
    def is_staff(self):
        return self.role == 'staff'

    @property
    def is_staff_or_official(self):
        return self.role in ('staff', 'official')


class Report(models.Model):
    """Reports submitted by residents to the barangay."""
    REPORT_TYPE_CHOICES = (
        ('complaint', 'Complaint'),
        ('incident', 'Incident'),
    )
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Resolved', 'Resolved'),
    )
    resident = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports')
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, default='complaint')
    category = models.CharField(max_length=100, default='General')
    title = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=200, blank=True, default='')
    evidence = models.FileField(upload_to='evidence/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_reports')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_report_type_display()}) by {self.resident.username}"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        role = 'official' if instance.is_superuser else 'resident'
        Profile.objects.create(user=instance, role=role)
    else:
        if instance.is_superuser:
            profile, _ = Profile.objects.get_or_create(user=instance)
            if profile.role != 'official':
                profile.role = 'official'
                profile.save()
