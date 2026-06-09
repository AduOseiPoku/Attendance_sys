# attendance/models.py

from django.db import models


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