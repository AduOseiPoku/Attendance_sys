# attendance/models.py

import uuid
from django.db import models
from django.contrib.auth.models import User


class Church(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )
    name = models.CharField(
        max_length=200,
        unique=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    is_student_church = models.BooleanField(
        default=False,
        help_text="Designates whether this church is a student fellowship/church."
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Churches"

    def __str__(self):
        return self.name


class GraduationYear(models.Model):
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="graduation_years"
    )
    year = models.CharField(
        max_length=100,
        help_text="e.g., Year 1, Year 2, Class of 2028"
    )
    completion_date = models.DateField(
        help_text="The date when members of this class complete school."
    )

    class Meta:
        ordering = ["completion_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["church", "year"],
                name="unique_church_graduation_year"
            )
        ]

    def __str__(self):
        return f"{self.year} (Ends: {self.completion_date})"


class Member(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="members",
        null=True,
        blank=True
    )
    graduation_year = models.ForeignKey(
        GraduationYear,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
        help_text="The student's graduation cohort."
    )

    # Optimized for name lookups
    name = models.CharField(
        max_length=100,
        db_index=True
    )

    # Phone number is unique per church, handled via Meta constraints
    phone_number = models.CharField(
        max_length=20,
        db_index=True
    )

    emergency_phone_number = models.CharField(
        max_length=20,
        blank=True,
        default=''
    )

    address = models.TextField(
        blank=True,
        default=''
    )

    # Optional church ministry/department
    department = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    # Soft-delete flag — inactive members are hidden from rosters but retain their attendance history
    is_active = models.BooleanField(
        default=True,
        db_index=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["church", "phone_number"],
                name="unique_church_member_phone"
            )
        ]

    def __str__(self):
        if self.church:
            return f"{self.name} ({self.phone_number}) - {self.church.name}"
        return f"{self.name} ({self.phone_number})"


class Event(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="events",
        null=True,
        blank=True
    )

    name = models.CharField(
        max_length=200
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    event_date = models.DateField()

    event_time = models.TimeField()

    is_active = models.BooleanField(
        default=True,
        db_index=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["-event_date", "-event_time"]

    def __str__(self):
        if self.church:
            return f"{self.name} ({self.event_date}) - {self.church.name}"
        return f"{self.name} ({self.event_date})"


class AttendanceLog(models.Model):
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="attendance_logs",
        null=True,
        blank=True
    )

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

    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="owners",
        null=True,
        blank=True
    )

    # NOTE: church_name field removed — use the church_name property below instead.
    # The property always reads from the linked Church record, preventing data drift.

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def church_name(self):
        """Always derived from the linked Church — never out of sync."""
        return self.church.name if self.church else "My Church"

    def __str__(self):
        return f"Owner: {self.user.username} ({self.church_name})"
