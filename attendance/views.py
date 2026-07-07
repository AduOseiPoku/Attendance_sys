# attendance/views.py
import re
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from urllib.parse import urlencode
from django.http import HttpResponse, HttpResponseNotAllowed
from django.views.decorators.http import require_POST
from django.db import IntegrityError
from django.db.models import Count, Q
from django.contrib.auth import authenticate, login, logout
from .models import Member, Event, AttendanceLog, ChurchOwner, Church
from .decorators import owner_required


def normalize_phone(phone):
    """
    Strips away all non-numeric characters.
    Example: '+233 (241) 234-567' -> '233241234567'
    """
    if not phone:
        return ""
    return re.sub(r'\D', '', phone)


def mask_phone(phone):
    """Hide all digits except the last 4."""
    if not phone or len(phone) <= 4:
        return phone
    return "*" * (len(phone) - 4) + phone[-4:]


def scan_landing(request, event_uuid):
    """Main entry point handling check-ins, exact/partial matches, and naming collisions."""
    event = get_object_or_404(Event, uuid=event_uuid)
    church = event.church

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        raw_phone = request.POST.get("phone_number", "").strip()
        phone = normalize_phone(raw_phone)

        if not phone or not name:
            return render(request, "attendance/scan_landing.html", {
                "event": event,
                "error": "Both Name and Phone Number are required."
            })

        # Scenario 1: Direct unique lookup based on phone index (per church)
        member = Member.objects.filter(church=church, phone_number=phone).first()

        if member:
            # Case A: Names match perfectly
            if member.name.lower() == name.lower():
                log, created = AttendanceLog.objects.get_or_create(
                    member=member, 
                    event=event,
                    defaults={"church": church}
                )
                status_msg = "Attendance recorded." if created else "You have already checked in for this event."
                return render(request, "attendance/success.html", {
                    "message": f"Welcome back, {member.name}! {status_msg}"
                })

            # Case B: Phone exists but user typed a different name
            return render(request, "attendance/name_suggestion.html", {
                "member": member,
                "event": event,
                "typed_name": name,
                "typed_phone": raw_phone,
            })

        # Scenario 2: Handle Duplicate Names / Clashing Profiles (per church)
        name_matches = Member.objects.filter(church=church, name__iexact=name)

        if name_matches.exists():
            if name_matches.count() == 1:
                # Only one person with this name exists -> Suggest correcting phone info
                single_match = name_matches.first()
                return render(request, "attendance/phone_suggestion.html", {
                    "member": single_match,
                    "event": event,
                    "masked_phone": mask_phone(single_match.phone_number),
                    "typed_name": name,
                    "typed_phone": raw_phone,
                })
            else:
                # DUPLICATE-NAME HANDLING: Multiple members share this identical name
                members_data = [
                    {"id": m.id, "uuid": str(m.uuid), "masked_phone": mask_phone(m.phone_number)}
                    for m in name_matches
                ]
                return render(request, "attendance/duplicate_names.html", {
                    "name": name,
                    "event": event,
                    "members_data": members_data,
                    "typed_name": name,
                    "typed_phone": raw_phone,
                })

        # Scenario 3: Complete Stranger -> Route directly to Onboarding
        params = urlencode({"name": name, "phone": phone})
        return redirect(f"{reverse('attendance:onboard_member', args=[event.uuid])}?{params}")

    return render(request, "attendance/scan_landing.html", {"event": event})


def onboard_member(request, event_uuid):
    """Registers a completely new member while enforcing phone normalization."""
    event = get_object_or_404(Event, uuid=event_uuid)
    church = event.church

    suggested_name = request.GET.get("name", "")
    suggested_phone = normalize_phone(request.GET.get("phone", ""))

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        phone_number = normalize_phone(request.POST.get("phone_number", ""))
        emergency_phone_number = normalize_phone(request.POST.get("emergency_phone_number", ""))
        address = request.POST.get("address", "").strip()
        department = request.POST.get("department", "").strip()

        try:
            member, created = Member.objects.get_or_create(
                church=church,
                phone_number=phone_number,
                defaults={
                    "name": name,
                    "emergency_phone_number": emergency_phone_number,
                    "address": address,
                    "department": department
                }
            )
            
            log, log_created = AttendanceLog.objects.get_or_create(
                member=member, 
                event=event,
                defaults={"church": church}
            )
            status_msg = "Attendance recorded." if log_created else "You have already checked in for this event."

            return render(request, "attendance/success.html", {
                "message": f"Registration successful! Welcome to {event.name}. {status_msg}"
            })

        except IntegrityError:
            return render(request, "attendance/onboard.html", {
                "event": event,
                "suggested_name": name,
                "suggested_phone": phone_number,
                "error": "This phone number is already registered in our system."
            })

    return render(request, "attendance/onboard.html", {
        "event": event,
        "suggested_name": suggested_name,
        "suggested_phone": suggested_phone
    })


def confirm_identity(request, event_uuid, member_uuid):
    """Universal POST-secured view handling confirmation checks across resolve pipelines."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    event = get_object_or_404(Event, uuid=event_uuid)
    member = get_object_or_404(Member, uuid=member_uuid)

    log, created = AttendanceLog.objects.get_or_create(
        member=member, 
        event=event,
        defaults={"church": event.church}
    )
    status_msg = "Attendance recorded." if created else "You have already checked in for this event."

    return render(request, "attendance/success.html", {
        "message": f"Welcome back, {member.name}! {status_msg}"
    })


@require_POST
def quick_checkin(request, event_uuid):
    """Fast path: create or find a member and record attendance with one click."""
    event = get_object_or_404(Event, uuid=event_uuid)
    church = event.church
    name = request.POST.get("name", "").strip()
    raw_phone = request.POST.get("phone", "").strip()
    phone = normalize_phone(raw_phone)

    if not name or not phone:
        return render(request, "attendance/scan_landing.html", {"event": event, "error": "Name and phone required."})

    member, created = Member.objects.get_or_create(
        church=church,
        phone_number=phone,
        defaults={"name": name}
    )

    log, log_created = AttendanceLog.objects.get_or_create(
        member=member, 
        event=event,
        defaults={"church": church}
    )
    status_msg = "Attendance recorded." if log_created else "You have already checked in for this event."

    return render(request, "attendance/success.html", {"message": f"Welcome, {member.name}! {status_msg}"})


# ---------------------------------------------------------------------------
# Church Owner Dashboard Views
# ---------------------------------------------------------------------------

def owner_login(request):
    """Custom login page restricted to ChurchOwner accounts."""
    if request.user.is_authenticated and hasattr(request.user, "church_owner"):
        return redirect("attendance:owner_dashboard")

    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user is not None and hasattr(user, "church_owner"):
            login(request, user)
            return redirect("attendance:owner_dashboard")
        else:
            error = "Invalid credentials, or this account is not registered as a church owner."

    return render(request, "owner/login.html", {"error": error})


def owner_logout(request):
    """Logs out the church owner and redirects to login."""
    logout(request)
    return redirect("attendance:owner_login")


@owner_required
def owner_dashboard(request):
    """Main dashboard: stat cards, bar chart (per-event), line chart (trend over time), recent events."""
    owner = request.user.church_owner
    church = owner.church

    # --- Stat cards ---
    total_members   = Member.objects.filter(church=church).count()
    total_events    = Event.objects.filter(church=church).count()
    total_checkins  = AttendanceLog.objects.filter(church=church).count()

    # Avg attendance rate: (total check-ins / possible check-ins) * 100
    possible = total_members * total_events
    avg_rate = round((total_checkins / possible * 100), 1) if possible > 0 else 0

    # --- Chart data: last 5 events ordered chronologically for both charts ---
    last_5_events = list(
        Event.objects.filter(church=church)
        .annotate(attendee_count=Count("attendance_logs"))
        .order_by("-event_date", "-event_time")[:5]
    )
    last_5_events.reverse()

    chart_labels = [f"{e.name} ({e.event_date})" for e in last_5_events]
    chart_data   = [e.attendee_count for e in last_5_events]

    # --- Recent events table (last 5, newest first) ---
    recent_events = (
        Event.objects.filter(church=church)
        .annotate(attendee_count=Count("attendance_logs"))
        .order_by("-event_date", "-event_time")[:5]
    )

    context = {
        "owner": owner,
        "total_members":  total_members,
        "total_events":   total_events,
        "total_checkins": total_checkins,
        "avg_rate":       avg_rate,
        "chart_labels":   json.dumps(chart_labels),
        "chart_data":     json.dumps(chart_data),
        "recent_events":  recent_events,
    }
    return render(request, "owner/dashboard.html", context)


@owner_required
def owner_members(request):
    """Member list with search bar and department filter dropdown."""
    owner = request.user.church_owner
    church = owner.church

    search     = request.GET.get("search", "").strip()
    department = request.GET.get("department", "").strip()

    members_qs = Member.objects.filter(church=church).annotate(total_attendances=Count("attendance_logs"))

    if search:
        members_qs = members_qs.filter(
            Q(name__icontains=search) | Q(phone_number__icontains=search)
        )

    if department:
        members_qs = members_qs.filter(department=department)

    members_qs = members_qs.order_by("-total_attendances")

    # Populate the department dropdown with all distinct non-null department values
    departments = (
        Member.objects.filter(church=church)
        .exclude(department__isnull=True)
        .exclude(department="")
        .values_list("department", flat=True)
        .distinct()
        .order_by("department")
    )

    context = {
        "owner":        owner,
        "members":      members_qs,
        "departments":  departments,
        "search":       search,
        "department":   department,
        "total_events": Event.objects.filter(church=church).count(),
    }
    return render(request, "owner/members.html", context)


@owner_required
def owner_event_detail(request, pk):
    """Per-event Present / Absent roster with attendance percentage."""
    owner = request.user.church_owner
    church = owner.church
    event = get_object_or_404(Event, pk=pk, church=church)

    present_member_ids = AttendanceLog.objects.filter(event=event).values_list("member_id", flat=True)
    present_members    = Member.objects.filter(church=church, id__in=present_member_ids).order_by("name")
    absent_members     = Member.objects.filter(church=church).exclude(id__in=present_member_ids).order_by("name")

    total    = Member.objects.filter(church=church).count()
    pct      = round(present_members.count() / total * 100, 1) if total > 0 else 0

    context = {
        "owner":           owner,
        "event":           event,
        "present_members": present_members,
        "absent_members":  absent_members,
        "present_count":   present_members.count(),
        "absent_count":    absent_members.count(),
        "attendance_pct":  pct,
    }
    return render(request, "owner/event_detail.html", context)


@owner_required
@require_POST
def owner_toggle_event_status(request, pk):
    """Toggles an event between active and closed."""
    owner = request.user.church_owner
    event = get_object_or_404(Event, pk=pk, church=owner.church)
    
    event.is_active = not event.is_active
    event.save(update_fields=["is_active"])
    
    return redirect("attendance:owner_event_detail", pk=event.pk)


@owner_required
def owner_create_event(request):
    """Allow church owners to create a new event from their dashboard."""
    owner = request.user.church_owner
    church = owner.church

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        event_date = request.POST.get("event_date", "").strip()
        event_time = request.POST.get("event_time", "").strip()
        is_active = request.POST.get("is_active") == "on"

        errors = []
        if not name:
            errors.append("Event name is required.")
        if not event_date:
            errors.append("Event date is required.")
        if not event_time:
            errors.append("Event time is required.")

        if errors:
            return render(request, "owner/create_event.html", {
                "owner": owner,
                "errors": errors,
                "form_data": {
                    "name": name,
                    "description": description,
                    "event_date": event_date,
                    "event_time": event_time,
                    "is_active": is_active,
                },
            })

        from datetime import date, time as dt_time

        try:
            Event.objects.create(
                church=church,
                name=name,
                description=description or None,
                event_date=event_date,
                event_time=event_time,
                is_active=is_active,
            )
        except Exception as e:
            return render(request, "owner/create_event.html", {
                "owner": owner,
                "errors": [f"Could not create event: {e}"],
                "form_data": {
                    "name": name,
                    "description": description,
                    "event_date": event_date,
                    "event_time": event_time,
                    "is_active": is_active,
                },
            })

        return redirect("attendance:owner_dashboard")

    return render(request, "owner/create_event.html", {"owner": owner})


def global_landing(request):
    """Renders the global entry page for selecting a church."""
    churches = Church.objects.all()
    return render(request, "attendance/global_landing.html", {
        "churches": churches,
    })


def church_events(request, church_uuid):
    """Renders a dedicated page displaying active events for the selected church."""
    church = get_object_or_404(Church, uuid=church_uuid)
    events = Event.objects.filter(church=church, is_active=True).order_by("-event_date", "-event_time")
    return render(request, "attendance/church_events.html", {
        "church": church,
        "events": events,
    })


def get_church_events(request, church_uuid):
    """API endpoint returning events for a specific church as JSON."""
    church = get_object_or_404(Church, uuid=church_uuid)
    events = Event.objects.filter(church=church, is_active=True).order_by("-event_date", "-event_time")[:3]
    data = [
        {"id": str(event.uuid), "name": f"{event.name} ({event.event_date})"}
        for event in events
    ]
    from django.http import JsonResponse
    return JsonResponse({"events": data})