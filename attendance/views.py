# attendance/views.py
import re
import csv
import json
import logging
from datetime import date as dt_date, time as dt_time
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from urllib.parse import urlencode
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.views.decorators.http import require_POST
from django.db import IntegrityError
from django.db.models import Count, Q
from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator
# pyrefly: ignore [missing-import]
from django_ratelimit.decorators import ratelimit
from .models import Member, Event, AttendanceLog, ChurchOwner, Church, GraduationYear, Department
from .decorators import owner_required

logger = logging.getLogger(__name__)


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


@ratelimit(key='ip', rate='10/m', method='POST', block=True)
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
                logger.info(f"Check-in: '{member.name}' (ID:{member.id}) for event '{event.name}' — {status_msg}")
                return render(request, "attendance/success.html", {
                    "message": f"Welcome back, {member.name}! {status_msg}",
                    "event": event,
                })

            # Case B: Phone exists but user typed a different name
            logger.warning(f"Name mismatch on check-in for event '{event.name}': typed '{name}', registered as '{member.name}' (phone: ...{member.phone_number[-4:]})")
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
        is_visitor = request.POST.get("is_visitor") == "on"
        params_dict = {"name": name, "phone": phone}
        if is_visitor:
            params_dict["is_visitor"] = "true"
        params = urlencode(params_dict)
        return redirect(f"{reverse('attendance:onboard_member', args=[event.uuid])}?{params}")

    return render(request, "attendance/scan_landing.html", {"event": event})


@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def onboard_member(request, event_uuid):
    """Registers a completely new member while enforcing phone normalization."""
    event = get_object_or_404(Event, uuid=event_uuid)
    church = event.church

    suggested_name = request.GET.get("name", "")
    suggested_phone = normalize_phone(request.GET.get("phone", ""))
    is_visitor_get = request.GET.get("is_visitor") == "true"

    graduation_years = []
    if church and church.is_student_church:
        graduation_years = church.graduation_years.filter(is_graduated=False)

    departments = []
    if church:
        departments = church.departments.all()

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        phone_number = normalize_phone(request.POST.get("phone_number", ""))
        emergency_phone_number = normalize_phone(request.POST.get("emergency_phone_number", ""))
        address = request.POST.get("address", "").strip()
        department_id = request.POST.get("department")
        is_visitor = request.POST.get("is_visitor") == "on"
        
        graduation_year_id = request.POST.get("graduation_year")
        graduation_year = None
        if church and church.is_student_church and graduation_year_id:
            try:
                graduation_year = church.graduation_years.get(id=graduation_year_id)
            except (ValueError, TypeError, GraduationYear.DoesNotExist):
                graduation_year = None

        department = None
        if church and department_id:
            try:
                department = church.departments.get(id=department_id)
            except (ValueError, TypeError, Department.DoesNotExist):
                department = None

        try:
            member, created = Member.objects.get_or_create(
                church=church,
                phone_number=phone_number,
                defaults={
                    "name": name,
                    "emergency_phone_number": emergency_phone_number,
                    "address": address,
                    "department": department,
                    "graduation_year": graduation_year,
                    "is_visitor": is_visitor
                }
            )
            
            log, log_created = AttendanceLog.objects.get_or_create(
                member=member, 
                event=event,
                defaults={"church": church}
            )
            status_msg = "Attendance recorded." if log_created else "You have already checked in for this event."

            if created:
                logger.info(f"Onboard: New member '{name}' registered for event '{event.name}' (church: '{church}').")
            else:
                logger.info(f"Onboard: Returning member '{member.name}' checked in for event '{event.name}'.")

            return render(request, "attendance/success.html", {
                "message": f"Registration successful! Welcome to {event.name}. {status_msg}",
                "event": event,
            })

        except IntegrityError:
            logger.warning(f"Onboard: Duplicate phone '{phone_number}' attempted for event '{event.name}'.")
            return render(request, "attendance/onboard.html", {
                "event": event,
                "error": "This phone number is already registered to another member.",
                "suggested_name": name,
                "suggested_phone": request.POST.get("phone_number", ""),
                "graduation_years": graduation_years,
                "departments": departments,
            })

    return render(request, "attendance/onboard.html", {
        "event": event,
        "suggested_name": suggested_name,
        "suggested_phone": suggested_phone,
        "is_visitor_get": is_visitor_get,
        "graduation_years": graduation_years,
        "departments": departments,
    })


@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def onboard_church_member(request, church_uuid):
    """Registers a new member for a church without an active event."""
    church = get_object_or_404(Church, uuid=church_uuid)

    suggested_name = request.GET.get("name", "")
    suggested_phone = normalize_phone(request.GET.get("phone", ""))
    is_visitor_get = request.GET.get("is_visitor") == "true"

    graduation_years = []
    if church.is_student_church:
        graduation_years = church.graduation_years.filter(is_graduated=False)

    departments = church.departments.all()

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        phone_number = normalize_phone(request.POST.get("phone_number", ""))
        emergency_phone_number = normalize_phone(request.POST.get("emergency_phone_number", ""))
        address = request.POST.get("address", "").strip()
        department_id = request.POST.get("department")
        is_visitor = request.POST.get("is_visitor") == "on"
        
        graduation_year_id = request.POST.get("graduation_year")
        graduation_year = None
        if church.is_student_church and graduation_year_id:
            try:
                graduation_year = church.graduation_years.get(id=graduation_year_id)
            except (ValueError, TypeError, GraduationYear.DoesNotExist):
                graduation_year = None

        department = None
        if department_id:
            try:
                department = church.departments.get(id=department_id)
            except (ValueError, TypeError, Department.DoesNotExist):
                department = None

        try:
            member, created = Member.objects.get_or_create(
                church=church,
                phone_number=phone_number,
                defaults={
                    "name": name,
                    "emergency_phone_number": emergency_phone_number,
                    "address": address,
                    "department": department,
                    "graduation_year": graduation_year,
                    "is_visitor": is_visitor
                }
            )
            
            if created:
                logger.info(f"Onboard: New member '{name}' registered for church '{church.name}'.")
            else:
                logger.info(f"Onboard: Returning member '{member.name}' attempted registration for church '{church.name}'.")

            return render(request, "attendance/success_church.html", {
                "message": f"Registration successful! Welcome to {church.name}.",
                "church": church,
            })

        except IntegrityError:
            logger.warning(f"Onboard: Duplicate phone '{phone_number}' attempted for church '{church.name}'.")
            return render(request, "attendance/onboard_church_member.html", {
                "church": church,
                "error": "This phone number is already registered to another member.",
                "suggested_name": name,
                "suggested_phone": request.POST.get("phone_number", ""),
                "graduation_years": graduation_years,
                "departments": departments,
            })

    return render(request, "attendance/onboard_church_member.html", {
        "church": church,
        "suggested_name": suggested_name,
        "suggested_phone": suggested_phone,
        "is_visitor_get": is_visitor_get,
        "graduation_years": graduation_years,
        "departments": departments,
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
    logger.info(f"Identity confirmed: '{member.name}' checked in for event '{event.name}' — {status_msg}")

    return render(request, "attendance/success.html", {
        "message": f"Welcome back, {member.name}! {status_msg}",
        "event": event,
    })


@ratelimit(key='ip', rate='10/m', method='POST', block=True)
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
        defaults={"name": name, "address": "", "emergency_phone_number": ""}
    )

    log, log_created = AttendanceLog.objects.get_or_create(
        member=member, 
        event=event,
        defaults={"church": church}
    )
    status_msg = "Attendance recorded." if log_created else "You have already checked in for this event."
    logger.info(f"Quick check-in: '{member.name}' for event '{event.name}' — {status_msg}")

    return render(request, "attendance/success.html", {"message": f"Welcome, {member.name}! {status_msg}", "event": event})


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
            logger.info(f"Owner login: '{username}' signed in successfully.")
            return redirect("attendance:owner_dashboard")
        else:
            logger.warning(f"Failed owner login attempt for username: '{username}'.")
            error = "Invalid credentials, or this account is not registered as a church owner."

    return render(request, "owner/login.html", {"error": error})


@require_POST
def owner_logout(request):
    """Logs out the church owner and redirects to login (POST only to prevent CSRF forced-logout)."""
    logger.info(f"Owner logout: '{request.user.username}' session ended.")
    logout(request)
    return redirect("attendance:owner_login")


@owner_required
def owner_dashboard(request):
    """Main dashboard: stat cards, bar chart (per-event), line chart (trend over time), recent events."""
    owner = request.user.church_owner
    church = owner.church

    # --- Stat cards ---
    total_members   = Member.objects.filter(church=church, is_active=True).count()
    total_events    = Event.objects.filter(church=church).count()
    total_checkins  = AttendanceLog.objects.filter(church=church).count()

    # Avg event fill rate: average of (attendees / active_members) per event
    # This is more meaningful than a global ratio as it accounts for per-event variation.
    if total_members > 0 and total_events > 0:
        avg_rate = round((total_checkins / total_events / total_members) * 100, 1)
    else:
        avg_rate = 0

    # --- Chart data: last 5 events ordered chronologically for both charts ---
    last_5_events = list(
        Event.objects.filter(church=church)
        .annotate(attendee_count=Count("attendance_logs"))
        .order_by("-event_date", "-event_time")[:5]
    )
    last_5_events.reverse()

    chart_labels = [[e.name, str(e.event_date)] for e in last_5_events]
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
    """Member list with search bar, department filter, graduation year filter, and pagination (50 per page)."""
    owner = request.user.church_owner
    church = owner.church

    search             = request.GET.get("search", "").strip()
    department_id      = request.GET.get("department", "").strip()
    graduation_year_id = request.GET.get("graduation_year", "").strip()

    members_qs = (
        Member.objects
        .filter(church=church, is_active=True)
        .select_related('church', 'graduation_year')
        .annotate(total_attendances=Count("attendance_logs"))
    )

    if search:
        members_qs = members_qs.filter(
            Q(name__icontains=search) | Q(phone_number__icontains=search)
        )

    if department_id:
        members_qs = members_qs.filter(department_id=department_id)

    if graduation_year_id:
        members_qs = members_qs.filter(graduation_year_id=graduation_year_id)

    members_qs = members_qs.order_by("-total_attendances")

    # Pagination — 50 members per page
    paginator = Paginator(members_qs, 50)
    page_obj  = paginator.get_page(request.GET.get("page"))

    # Populate the department dropdown with actual departments
    departments = church.departments.all()

    graduation_years = []
    if church.is_student_church:
        graduation_years = church.graduation_years.all()

    context = {
        "owner":              owner,
        "members":            page_obj,
        "page_obj":           page_obj,
        "is_paginated":       page_obj.has_other_pages(),
        "departments":        departments,
        "graduation_years":   graduation_years,
        "search":             search,
        "department_id":      department_id,
        "graduation_year_id": graduation_year_id,
        "total_events":       Event.objects.filter(church=church).count(),
    }
    return render(request, "owner/members.html", context)


@owner_required
def owner_event_detail(request, event_uuid):
    """Per-event Present / Absent roster with attendance percentage."""
    owner = request.user.church_owner
    church = owner.church
    event = get_object_or_404(Event, uuid=event_uuid, church=church)

    present_member_ids = AttendanceLog.objects.filter(event=event).values_list("member_id", flat=True)
    present_members = (
        Member.objects
        .filter(church=church, id__in=present_member_ids)
        .select_related('church')
        .order_by("name")
    )
    absent_members = (
        Member.objects
        .filter(church=church, is_active=True)
        .exclude(id__in=present_member_ids)
        .select_related('church')
        .order_by("name")
    )

    total         = Member.objects.filter(church=church, is_active=True).count()
    present_count = present_members.count()
    absent_count  = absent_members.count()
    pct           = round(present_count / total * 100, 1) if total > 0 else 0

    context = {
        "owner":           owner,
        "event":           event,
        "present_members": present_members,
        "absent_members":  absent_members,
        "present_count":   present_count,
        "absent_count":    absent_count,
        "attendance_pct":  pct,
    }
    return render(request, "owner/event_detail.html", context)


@owner_required
@require_POST
def owner_toggle_event_status(request, event_uuid):
    """Toggles an event between active and closed."""
    owner = request.user.church_owner
    event = get_object_or_404(Event, uuid=event_uuid, church=owner.church)
    
    event.is_active = not event.is_active
    event.save(update_fields=["is_active"])
    status_label = "opened" if event.is_active else "closed"
    logger.info(f"Event '{event.name}' {status_label} by owner '{request.user.username}'.")

    return redirect("attendance:owner_event_detail", event_uuid=event.uuid)


@owner_required
def owner_edit_event(request, event_uuid):
    """Allows church owners to edit an event's details from their dashboard."""
    owner = request.user.church_owner
    church = owner.church
    event = get_object_or_404(Event, uuid=event_uuid, church=church)

    if request.method == "POST":
        name        = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        event_date  = request.POST.get("event_date", "").strip()
        event_time  = request.POST.get("event_time", "").strip()
        is_active   = request.POST.get("is_active") == "on"

        errors = []
        parsed_date = parsed_time = None

        if not name:
            errors.append("Event name is required.")
        if not event_date:
            errors.append("Event date is required.")
        else:
            try:
                parsed_date = dt_date.fromisoformat(event_date)
            except ValueError:
                errors.append("Invalid date format. Please use the date picker.")
        if not event_time:
            errors.append("Event time is required.")
        else:
            try:
                parsed_time = dt_time.fromisoformat(event_time)
            except ValueError:
                errors.append("Invalid time format. Please use the time picker.")

        if errors:
            return render(request, "owner/edit_event.html", {
                "owner": owner,
                "event": event,
                "errors": errors,
                "form_data": {
                    "name": name,
                    "description": description,
                    "event_date": event_date,
                    "event_time": event_time,
                    "is_active": is_active,
                },
            })

        try:
            event.name        = name
            event.description = description or None
            event.event_date  = parsed_date
            event.event_time  = parsed_time
            event.is_active   = is_active
            event.save()
        except Exception as e:
            return render(request, "owner/edit_event.html", {
                "owner": owner,
                "event": event,
                "errors": [f"Could not update event: {e}"],
                "form_data": {
                    "name": name,
                    "description": description,
                    "event_date": event_date,
                    "event_time": event_time,
                    "is_active": is_active,
                },
            })

        return redirect("attendance:owner_event_detail", event_uuid=event.uuid)

    # GET request: pre-populate fields
    form_data = {
        "name": event.name,
        "description": event.description or "",
        "event_date": event.event_date.strftime("%Y-%m-%d") if event.event_date else "",
        "event_time": event.event_time.strftime("%H:%M") if event.event_time else "",
        "is_active": event.is_active,
    }
    return render(request, "owner/edit_event.html", {
        "owner": owner,
        "event": event,
        "form_data": form_data
    })


@owner_required
def owner_create_event(request):
    """Allow church owners to create a new event from their dashboard."""
    owner = request.user.church_owner
    church = owner.church

    if request.method == "POST":
        name        = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        event_date  = request.POST.get("event_date", "").strip()
        event_time  = request.POST.get("event_time", "").strip()
        is_active   = request.POST.get("is_active") == "on"

        errors = []
        parsed_date = parsed_time = None

        if not name:
            errors.append("Event name is required.")
        if not event_date:
            errors.append("Event date is required.")
        else:
            try:
                parsed_date = dt_date.fromisoformat(event_date)
            except ValueError:
                errors.append("Invalid date format. Please use the date picker.")
        if not event_time:
            errors.append("Event time is required.")
        else:
            try:
                parsed_time = dt_time.fromisoformat(event_time)
            except ValueError:
                errors.append("Invalid time format. Please use the time picker.")

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

        try:
            Event.objects.create(
                church=church,
                name=name,
                description=description or None,
                event_date=parsed_date,
                event_time=parsed_time,
                is_active=is_active,
            )
            logger.info(f"Event created: '{name}' on {parsed_date} by owner '{request.user.username}' (church: '{church}').")
        except Exception as e:
            logger.exception(f"Failed to create event '{name}' for church '{church}': {e}")
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
    return JsonResponse({"events": data})


# ---------------------------------------------------------------------------
# Events List Page (Phase 3.4)
# ---------------------------------------------------------------------------

@owner_required
def owner_events(request):
    """Paginated list of all events for this church with optional search and status filter."""
    owner = request.user.church_owner
    church = owner.church

    search = request.GET.get("search", "").strip()
    status = request.GET.get("status", "").strip()  # 'active' | 'closed' | ''

    events_qs = (
        Event.objects.filter(church=church)
        .annotate(attendee_count=Count("attendance_logs"))
        .order_by("-event_date", "-event_time")
    )

    if search:
        events_qs = events_qs.filter(name__icontains=search)
    if status == "active":
        events_qs = events_qs.filter(is_active=True)
    elif status == "closed":
        events_qs = events_qs.filter(is_active=False)

    paginator = Paginator(events_qs, 20)
    page_obj  = paginator.get_page(request.GET.get("page"))

    return render(request, "owner/events.html", {
        "owner":        owner,
        "page_obj":     page_obj,
        "events":       page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "search":       search,
        "status":       status,
    })


# ---------------------------------------------------------------------------
# Member Edit & Soft-Delete (Phase 4.2 & 4.3)
# ---------------------------------------------------------------------------

@owner_required
def owner_edit_member(request, member_uuid):
    """Allows a church owner to edit a member's profile details."""
    owner = request.user.church_owner
    church = owner.church
    member = get_object_or_404(Member, uuid=member_uuid, church=church)

    graduation_years = []
    if church and church.is_student_church:
        graduation_years = church.graduation_years.all()
        
    departments = church.departments.all()

    if request.method == "POST":
        name                  = request.POST.get("name", "").strip()
        phone_number          = normalize_phone(request.POST.get("phone_number", ""))
        emergency_phone       = normalize_phone(request.POST.get("emergency_phone_number", ""))
        address               = request.POST.get("address", "").strip()
        department_id         = request.POST.get("department")
        graduation_year_id    = request.POST.get("graduation_year")

        graduation_year = None
        if church and church.is_student_church and graduation_year_id:
            try:
                graduation_year = church.graduation_years.get(id=graduation_year_id)
            except (ValueError, TypeError, GraduationYear.DoesNotExist):
                graduation_year = None

        department = None
        if department_id:
            try:
                department = church.departments.get(id=department_id)
            except (ValueError, TypeError, Department.DoesNotExist):
                department = None

        errors = []
        if not name:
            errors.append("Name is required.")
        if not phone_number:
            errors.append("Phone number is required.")

        if errors:
            return render(request, "owner/edit_member.html", {
                "owner": owner, "member": member, "errors": errors,
                "graduation_years": graduation_years,
                "departments": departments,
                "form_data": {
                    "name": name, "phone_number": phone_number,
                    "emergency_phone_number": emergency_phone,
                    "address": address, "department_id": department_id,
                    "graduation_year_id": graduation_year_id,
                },
            })

        try:
            member.name                  = name
            member.phone_number          = phone_number
            member.emergency_phone_number = emergency_phone
            member.address               = address
            member.department            = department
            member.graduation_year       = graduation_year
            member.save()
            logger.info(f"Member updated: '{name}' (ID:{member.id}) by owner '{request.user.username}'.")
        except Exception as e:
            logger.exception(f"Failed to update member '{name}' (ID:{member.id}): {e}")
            return render(request, "owner/edit_member.html", {
                "owner": owner, "member": member,
                "graduation_years": graduation_years,
                "errors": [f"Could not update member: {e}"],
            })

        return redirect("attendance:owner_members")

    form_data = {
        "name":                   member.name,
        "phone_number":           member.phone_number,
        "emergency_phone_number": member.emergency_phone_number,
        "address":                member.address,
        "department_id":          member.department_id,
        "graduation_year_id":     member.graduation_year_id,
    }
    return render(request, "owner/edit_member.html", {
        "owner": owner, "member": member, "form_data": form_data, 
        "graduation_years": graduation_years, "departments": departments
    })


@owner_required
@require_POST
def owner_deactivate_member(request, member_uuid):
    """Soft-deletes a member by setting is_active=False, preserving their attendance history."""
    owner = request.user.church_owner
    member = get_object_or_404(Member, uuid=member_uuid, church=owner.church)
    member.is_active = False
    member.save(update_fields=["is_active"])
    logger.info(f"Member deactivated: '{member.name}' (ID:{member.id}) by owner '{request.user.username}'.")
    return redirect("attendance:owner_members")


@owner_required
def owner_graduation_years(request):
    """Allows the church owner to view and configure graduation cohorts."""
    owner = request.user.church_owner
    church = owner.church

    # Ensure this church is configured as a student church to access this settings view
    if not church.is_student_church:
        return redirect("attendance:owner_dashboard")

    errors = []
    if request.method == "POST":
        year_str = request.POST.get("year", "").strip()
        completion_date_str = request.POST.get("completion_date", "").strip()

        if not year_str or not completion_date_str:
            errors.append("Both year and completion date are required.")
        else:
            try:
                # Check for duplicate year label in this church case-insensitively
                if church.graduation_years.filter(year__iexact=year_str).exists():
                    errors.append(f"Graduation cohort '{year_str}' is already registered.")
                else:
                    GraduationYear.objects.create(
                        church=church,
                        year=year_str,
                        completion_date=completion_date_str
                    )
                    logger.info(f"Cohort created: '{year_str}' (completion: {completion_date_str}) for church '{church}' by owner '{request.user.username}'.")
                    return redirect("attendance:owner_graduation_years")
            except Exception as e:
                logger.exception(f"Failed to create cohort '{year_str}' for church '{church}': {e}")
                errors.append(f"Error saving graduation year: {e}")

    # Fetch active cohorts with annotate count of active students ordered by completion date
    graduation_years = (
        church.graduation_years
        .annotate(student_count=Count("members", filter=Q(members__is_active=True)))
        .order_by("completion_date")
    )

    return render(request, "owner/graduation_years.html", {
        "owner": owner,
        "graduation_years": graduation_years,
        "errors": errors,
    })


@owner_required
@require_POST
def owner_delete_graduation_year(request, year_id):
    """Deletes a graduation cohort."""
    owner = request.user.church_owner
    church = owner.church
    
    # Ensure this cohort belongs to this church
    cohort = get_object_or_404(GraduationYear, id=year_id, church=church)
    cohort_label = cohort.year
    cohort.delete()
    logger.warning(f"Cohort deleted: '{cohort_label}' from church '{church}' by owner '{request.user.username}'.")

    return redirect("attendance:owner_graduation_years")


@owner_required
def owner_edit_graduation_year(request, year_id):
    """Allows the church owner to edit a cohort's name and completion date."""
    owner = request.user.church_owner
    church = owner.church

    if not church or not church.is_student_church:
        return redirect("attendance:owner_dashboard")

    cohort = get_object_or_404(GraduationYear, id=year_id, church=church)
    errors = []

    if request.method == "POST":
        year_str = request.POST.get("year", "").strip()
        completion_date_str = request.POST.get("completion_date", "").strip()
        is_graduated = request.POST.get("is_graduated") == "on"

        if not year_str or not completion_date_str:
            errors.append("Both year/class name and completion date are required.")
        else:
            try:
                # Check for duplicate year label in this church case-insensitively, excluding current cohort
                if church.graduation_years.filter(year__iexact=year_str).exclude(id=year_id).exists():
                    errors.append(f"Graduation cohort '{year_str}' is already registered.")
                else:
                    old_label = cohort.year
                    cohort.year = year_str
                    cohort.completion_date = completion_date_str
                    cohort.is_graduated = is_graduated
                    cohort.save()
                    logger.info(f"Cohort updated: '{old_label}' → '{year_str}' (completion: {completion_date_str}, graduated: {is_graduated}) by owner '{request.user.username}'.")
                    return redirect("attendance:owner_graduation_years")
            except Exception as e:
                logger.exception(f"Failed to update cohort (ID:{year_id}): {e}")
                errors.append(f"Error updating graduation cohort: {e}")

    form_data = {
        "year": cohort.year,
        "completion_date": cohort.completion_date.strftime("%Y-%m-%d") if cohort.completion_date else "",
        "is_graduated": cohort.is_graduated
    }

    return render(request, "owner/edit_graduation_year.html", {
        "owner": owner,
        "cohort": cohort,
        "errors": errors,
        "form_data": form_data
    })


# ---------------------------------------------------------------------------
# Department Management
# ---------------------------------------------------------------------------

@owner_required
def owner_departments(request):
    """Allows the church owner to view and configure departments."""
    owner = request.user.church_owner
    church = owner.church

    errors = []
    if request.method == "POST":
        name = request.POST.get("name", "").strip()

        if not name:
            errors.append("Department name is required.")
        else:
            try:
                # Check for duplicate department name in this church case-insensitively
                if church.departments.filter(name__iexact=name).exists():
                    errors.append(f"Department '{name}' is already registered.")
                else:
                    Department.objects.create(church=church, name=name)
                    logger.info(f"Department created: '{name}' for church '{church}' by owner '{request.user.username}'.")
                    return redirect("attendance:owner_departments")
            except Exception as e:
                logger.exception(f"Failed to create department '{name}' for church '{church}': {e}")
                errors.append(f"Error saving department: {e}")

    departments = church.departments.annotate(
        member_count=Count("members", filter=Q(members__is_active=True))
    ).order_by("name")

    return render(request, "owner/departments.html", {
        "owner": owner,
        "departments": departments,
        "errors": errors,
    })


@owner_required
@require_POST
def owner_delete_department(request, dept_id):
    """Deletes a department."""
    owner = request.user.church_owner
    church = owner.church
    
    dept = get_object_or_404(Department, id=dept_id, church=church)
    dept_name = dept.name
    dept.delete()
    logger.warning(f"Department deleted: '{dept_name}' from church '{church}' by owner '{request.user.username}'.")

    return redirect("attendance:owner_departments")


@owner_required
def owner_edit_department(request, dept_id):
    """Allows the church owner to rename a department."""
    owner = request.user.church_owner
    church = owner.church

    dept = get_object_or_404(Department, id=dept_id, church=church)
    errors = []

    if request.method == "POST":
        name = request.POST.get("name", "").strip()

        if not name:
            errors.append("Department name is required.")
        else:
            try:
                if church.departments.filter(name__iexact=name).exclude(id=dept_id).exists():
                    errors.append(f"Department '{name}' is already registered.")
                else:
                    old_name = dept.name
                    dept.name = name
                    dept.save()
                    logger.info(f"Department updated: '{old_name}' → '{name}' by owner '{request.user.username}'.")
                    return redirect("attendance:owner_departments")
            except Exception as e:
                logger.exception(f"Failed to update department (ID:{dept_id}): {e}")
                errors.append(f"Error updating department: {e}")

    return render(request, "owner/edit_department.html", {
        "owner": owner,
        "dept": dept,
        "errors": errors,
        "form_data": {"name": dept.name}
    })

# ---------------------------------------------------------------------------
# CSV Export (Phase 4.4)
# ---------------------------------------------------------------------------

@owner_required
def owner_export_event_csv(request, event_uuid):
    """Exports the attendance roster for an event as a downloadable CSV file."""
    owner = request.user.church_owner
    church = owner.church
    event = get_object_or_404(Event, uuid=event_uuid, church=church)

    response = HttpResponse(content_type="text/csv")
    filename = f"{event.name}_{event.event_date}_attendance.csv".replace(" ", "_")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(["Name", "Phone Number", "Department", "Check-in Time"])

    logs = (
        AttendanceLog.objects
        .filter(event=event)
        .select_related("member")
        .order_by("member__name")
    )
    for log in logs:
        writer.writerow([
            log.member.name,
            log.member.phone_number,
            log.member.department or "",
            log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        ])

    return response


# ---------------------------------------------------------------------------
# 429 Rate Limit Error Handler
# ---------------------------------------------------------------------------

def ratelimit_error(request, exception=None):
    """Renders a friendly 429 Too Many Requests page when a rate limit is hit."""
    return render(request, "attendance/ratelimit.html", status=429)
