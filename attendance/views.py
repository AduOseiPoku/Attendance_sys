from django.shortcuts import render

# Create your views here.
# attendance/views.py
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from urllib.parse import urlencode
from django.http import HttpResponse, HttpResponseNotAllowed
from django.views.decorators.http import require_POST
from django.db import IntegrityError
from .models import Member, Event, AttendanceLog


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


def scan_landing(request, event_id):
    """Main entry point handling check-ins, exact/partial matches, and naming collisions."""
    event = get_object_or_404(Event, id=event_id)

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        raw_phone = request.POST.get("phone_number", "").strip()
        phone = normalize_phone(raw_phone)

        if not phone or not name:
            return render(request, "attendance/scan_landing.html", {
                "event": event,
                "error": "Both Name and Phone Number are required."
            })

        # Scenario 1: Direct unique lookup based on phone index
        member = Member.objects.filter(phone_number=phone).first()

        if member:
            # Case A: Names match perfectly
            if member.name.lower() == name.lower():
                log, created = AttendanceLog.objects.get_or_create(member=member, event=event)
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

        # Scenario 2: Handle Duplicate Names / Clashing Profiles
        # Search using case-insensitive lookups optimized by our new name database index
        name_matches = Member.objects.filter(name__iexact=name)

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
                # Send them to a secure selector layout displaying masked parameters
                members_data = [
                    {"id": m.id, "masked_phone": mask_phone(m.phone_number)}
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
        return redirect(f"{reverse('onboard_member', args=[event.id])}?{params}")

    return render(request, "attendance/scan_landing.html", {"event": event})


def onboard_member(request, event_id):
    """Registers a completely new member while enforcing phone normalization."""
    event = get_object_or_404(Event, id=event_id)

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
                phone_number=phone_number,
                defaults={
                    "name": name,
                    "emergency_phone_number": emergency_phone_number,
                    "address": address,
                    "department": department
                }
            )
            
            log, log_created = AttendanceLog.objects.get_or_create(member=member, event=event)
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


def confirm_identity(request, event_id, member_id):
    """Universal POST-secured view handling confirmation checks across resolve pipelines."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    event = get_object_or_404(Event, id=event_id)
    member = get_object_or_404(Member, id=member_id)

    log, created = AttendanceLog.objects.get_or_create(member=member, event=event)
    status_msg = "Attendance recorded." if created else "You have already checked in for this event."

    return render(request, "attendance/success.html", {
        "message": f"Welcome back, {member.name}! {status_msg}"
    })


@require_POST
def quick_checkin(request, event_id):
    """Fast path: create or find a member and record attendance with one click."""
    event = get_object_or_404(Event, id=event_id)
    name = request.POST.get("name", "").strip()
    raw_phone = request.POST.get("phone", "").strip()
    phone = normalize_phone(raw_phone)

    if not name or not phone:
        return render(request, "attendance/scan_landing.html", {"event": event, "error": "Name and phone required."})

    member, created = Member.objects.get_or_create(
        phone_number=phone,
        defaults={"name": name}
    )

    log, log_created = AttendanceLog.objects.get_or_create(member=member, event=event)
    status_msg = "Attendance recorded." if log_created else "You have already checked in for this event."

    return render(request, "attendance/success.html", {"message": f"Welcome, {member.name}! {status_msg}"})