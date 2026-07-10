from django.contrib import admin
from .models import Member, Event, AttendanceLog, ChurchOwner, Church


@admin.register(Church)
class ChurchAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
    readonly_fields = ("created_at",)


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("name", "phone_number", "church", "department", "created_at")
    search_fields = ("name", "phone_number")
    list_filter = ("church", "department")
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "church", "event_date", "event_time", "is_active", "created_at")
    list_editable = ("is_active",)
    search_fields = ("name", "description")
    list_filter = ("church", "is_active", "event_date")
    date_hierarchy = "event_date"
    ordering = ("-event_date", "-event_time")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = ("member", "event", "church", "timestamp")
    search_fields = ("member__name", "member__phone_number", "event__name")
    list_filter = ("church", "event")
    raw_id_fields = ("member", "event")
    readonly_fields = ("timestamp",)
    ordering = ("-timestamp",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('member', 'event', 'church')


@admin.register(ChurchOwner)
class ChurchOwnerAdmin(admin.ModelAdmin):
    list_display = ("user", "church", "created_at")
    search_fields = ("user__username",)
    list_filter = ("church",)
    readonly_fields = ("created_at",)


# --- Inline integration to allow pairing user to church on the same page ---
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

class ChurchOwnerInline(admin.StackedInline):
    model = ChurchOwner
    can_delete = False
    verbose_name_plural = 'Church Owner Details'
    fk_name = 'user'

admin.site.unregister(User)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (ChurchOwnerInline,)