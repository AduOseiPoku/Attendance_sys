from django.contrib import admin
from .models import Member, Event, AttendanceLog, ChurchOwner


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("name", "phone_number", "department", "created_at")
    search_fields = ("name", "phone_number")
    list_filter = ("department",)
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "event_date", "event_time", "created_at")
    search_fields = ("name", "description")
    list_filter = ("event_date",)
    date_hierarchy = "event_date"
    ordering = ("-event_date", "-event_time")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = ("member", "event", "timestamp")
    search_fields = ("member__name", "member__phone_number", "event__name")
    list_filter = ("event",)
    raw_id_fields = ("member", "event")
    readonly_fields = ("timestamp",)
    ordering = ("-timestamp",)


@admin.register(ChurchOwner)
class ChurchOwnerAdmin(admin.ModelAdmin):
    list_display = ("user", "church_name", "created_at")
    search_fields = ("user__username", "church_name")
    readonly_fields = ("created_at",)