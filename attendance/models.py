# attendance/models.py

from django.db import models
from django.contrib.auth.models import User


class Member(models.Model):
    # Optimized for name lookups
    name = models.CharField(
        max_length=100,
        db_index=True
    )

    # Main unique identifier
    phone_number = models.CharField(
        max_length=20,
        unique=True,
        db_index=True
    )

    emergency_phone_number = models.CharField(
        max_length=20
    )

    address = models.TextField()

    # Optional church ministry/department
    department = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.phone_number})"


class Event(models.Model):
    name = models.CharField(
        max_length=200
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    event_date = models.DateField()

    event_time = models.TimeField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["-event_date", "-event_time"]

    def __str__(self):
        return f"{self.name} ({self.event_date})"


class AttendanceLog(models.Model):
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="attendance_logs"
    )

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="attendance_logs"
    )

    timestamp = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["member", "event"],
                name="unique_member_event_attendance"
            )
        ]
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.member.name} - {self.event.name}"


class ChurchOwner(models.Model):
    """
    A dedicated owner account for the church pastor/administrator.
    Linked to Django's built-in User model via OneToOne so the owner
    has their own login credentials separate from the superuser.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="church_owner"
    )

    church_name = models.CharField(
        max_length=200,
        default="My Church"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Owner: {self.user.username} ({self.church_name})"