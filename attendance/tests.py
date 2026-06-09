from datetime import date, time
from urllib.parse import quote, urlencode

from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import AttendanceLog, Event, Member

# Minimal in-memory templates so assertTemplateUsed works during tests
LOC_MEM_TEMPLATES = {
    "attendance/scan_landing.html": "<html>scan</html>",
    "attendance/success.html": "<html>success: {{ message }}</html>",
    "attendance/name_suggestion.html": "<html>name suggestion</html>",
    "attendance/phone_suggestion.html": "<html>phone suggestion {{ masked_phone }}</html>",
    "attendance/duplicate_names.html": "<html>duplicate names</html>",
    "attendance/onboard.html": "<html>onboard</html>",
}

# -------------------------
# Model tests (existing)
# -------------------------
class MemberModelTests(TestCase):
    def test_member_str_representation(self):
        member = Member.objects.create(
            name="John Doe",
            phone_number="+233500000001",
            emergency_phone_number="+233500000099",
            address="Accra",
            department="Choir",
        )
        self.assertEqual(str(member), "John Doe (+233500000001)")

    def test_member_ordering_by_name_ascending(self):
        Member.objects.create(
            name="Zoe",
            phone_number="+233500000010",
            emergency_phone_number="+233500000110",
            address="Address 1",
        )
        Member.objects.create(
            name="Alice",
            phone_number="+233500000011",
            emergency_phone_number="+233500000111",
            address="Address 2",
        )

        names = list(Member.objects.values_list("name", flat=True))
        self.assertEqual(names, ["Alice", "Zoe"])

    def test_phone_number_must_be_unique(self):
        Member.objects.create(
            name="First User",
            phone_number="+233500000020",
            emergency_phone_number="+233500000120",
            address="Address 1",
        )
        with self.assertRaises(IntegrityError):
            Member.objects.create(
                name="Second User",
                phone_number="+233500000020",  # duplicate
                emergency_phone_number="+233500000121",
                address="Address 2",
            )

    def test_department_is_optional(self):
        member = Member.objects.create(
            name="No Department",
            phone_number="+233500000030",
            emergency_phone_number="+233500000130",
            address="Address 3",
        )
        self.assertIsNone(member.department)


class EventModelTests(TestCase):
    def test_event_str_representation(self):
        event = Event.objects.create(
            name="Sunday Service",
            event_date=date(2026, 6, 1),
            event_time=time(9, 0),
        )
        self.assertEqual(str(event), "Sunday Service (2026-06-01)")

    def test_event_ordering_by_date_then_time_desc(self):
        e1 = Event.objects.create(
            name="Earlier Day",
            event_date=date(2026, 5, 31),
            event_time=time(10, 0),
        )
        e2 = Event.objects.create(
            name="Later Time Same Day",
            event_date=date(2026, 6, 1),
            event_time=time(11, 0),
        )
        e3 = Event.objects.create(
            name="Earlier Time Same Day",
            event_date=date(2026, 6, 1),
            event_time=time(8, 0),
        )

        ordered_ids = list(Event.objects.values_list("id", flat=True))
        self.assertEqual(ordered_ids, [e2.id, e3.id, e1.id])


class AttendanceLogModelTests(TestCase):
    def setUp(self):
        self.member = Member.objects.create(
            name="Test Member",
            phone_number="+233500000040",
            emergency_phone_number="+233500000140",
            address="Address 4",
        )
        self.event = Event.objects.create(
            name="Youth Meeting",
            event_date=date(2026, 6, 2),
            event_time=time(18, 30),
        )

    def test_attendance_log_str_representation(self):
        log = AttendanceLog.objects.create(member=self.member, event=self.event)
        self.assertEqual(str(log), "Test Member - Youth Meeting")

    def test_unique_member_event_constraint(self):
        AttendanceLog.objects.create(member=self.member, event=self.event)
        with self.assertRaises(IntegrityError):
            AttendanceLog.objects.create(member=self.member, event=self.event)

    def test_related_names_work(self):
        log = AttendanceLog.objects.create(member=self.member, event=self.event)
        self.assertIn(log, self.member.attendance_logs.all())
        self.assertIn(log, self.event.attendance_logs.all())

    def test_cascade_delete_member_removes_attendance(self):
        AttendanceLog.objects.create(member=self.member, event=self.event)
        self.member.delete()
        self.assertEqual(AttendanceLog.objects.count(), 0)


# -------------------------
# View tests (Sprint 2 flows)
# -------------------------
@override_settings(
    TEMPLATES=[
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [],
            "APP_DIRS": False,
            "OPTIONS": {
                "loaders": [("django.template.loaders.locmem.Loader", LOC_MEM_TEMPLATES)],
                "context_processors": [
                    "django.template.context_processors.request",
                    "django.contrib.auth.context_processors.auth",
                    "django.contrib.messages.context_processors.messages",
                ],
            },
        }
    ]
)
class AttendanceSystemViewsTestCase(TestCase):
    def setUp(self):
        # client available as self.client from TestCase
        # Create baseline event (use actual field names)
        self.event = Event.objects.create(name="Sunday General Service", event_date=date.today(), event_time=time(9, 0))

        # Existing member with normalized phone
        self.existing_member = Member.objects.create(
            name="Kwame Mensah",
            phone_number="233241234567",
            emergency_phone_number="233207654321",
            address="123 Bethel Street, Accra",
        )

        # Duplicate-name profiles
        self.dup_member_1 = Member.objects.create(
            name="John Osei",
            phone_number="233241111111",
            emergency_phone_number="233209999999",
            address="Location Alpha",
        )
        self.dup_member_2 = Member.objects.create(
            name="John Osei",
            phone_number="233242222222",
            emergency_phone_number="233208888888",
            address="Location Beta",
        )

    def test_scan_landing_page_get(self):
        url = reverse("scan_landing", kwargs={"event_id": self.event.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "attendance/scan_landing.html")

    def test_exact_match_attendance_logging(self):
        url = reverse("scan_landing", kwargs={"event_id": self.event.id})
        post_data = {"name": "  kWaMe mEnSaH ", "phone_number": " +233 (241) 234-567 "}
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "attendance/success.html")
        self.assertTrue(AttendanceLog.objects.filter(member=self.existing_member, event=self.event).exists())

    def test_already_checked_in_status_message(self):
        AttendanceLog.objects.create(member=self.existing_member, event=self.event)
        url = reverse("scan_landing", kwargs={"event_id": self.event.id})
        post_data = {"name": "Kwame Mensah", "phone_number": "233241234567"}
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You have already checked in")

    def test_phone_exists_name_mismatch_suggestion(self):
        url = reverse("scan_landing", kwargs={"event_id": self.event.id})
        post_data = {"name": "Wrong Name", "phone_number": "233241234567"}
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "attendance/name_suggestion.html")

    def test_name_exists_phone_mismatch_suggestion(self):
        url = reverse("scan_landing", kwargs={"event_id": self.event.id})
        post_data = {"name": "Kwame Mensah", "phone_number": "233999999999"}
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "attendance/phone_suggestion.html")
        self.assertIn("masked_phone", response.context)

    def test_duplicate_name_collision_handling(self):
        url = reverse("scan_landing", kwargs={"event_id": self.event.id})
        post_data = {"name": "John Osei", "phone_number": "233000000000"}
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "attendance/duplicate_names.html")
        self.assertEqual(len(response.context["members_data"]), 2)

    def test_unknown_visitor_redirects_to_onboarding(self):
        url = reverse("scan_landing", kwargs={"event_id": self.event.id})
        post_data = {"name": "New Stranger", "phone_number": "233555555555"}
        response = self.client.post(url, post_data)
        expected = reverse('onboard_member', kwargs={'event_id': self.event.id}) + "?" + urlencode({'name': 'New Stranger', 'phone': '233555555555'})
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_onboard_member_submission(self):
        url = reverse("onboard_member", kwargs={"event_id": self.event.id})
        post_data = {
            "name": "Adu Poku",
            "phone_number": "+233 (50) 111-2222",
            "emergency_phone_number": "0240000000",
            "address": "Kumasi, Ghana",
            "department": "Media Team",
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "attendance/success.html")

        new_member = Member.objects.get(phone_number="233501112222")
        self.assertEqual(new_member.name, "Adu Poku")
        self.assertTrue(AttendanceLog.objects.filter(member=new_member, event=self.event).exists())

    def test_secure_identity_confirmation_post_only(self):
        url = reverse("confirm_identity", kwargs={"event_id": self.event.id, "member_id": self.existing_member.id})
        get_response = self.client.get(url)
        self.assertEqual(get_response.status_code, 405)
        post_response = self.client.post(url)
        self.assertEqual(post_response.status_code, 200)
        self.assertTrue(AttendanceLog.objects.filter(member=self.existing_member, event=self.event).exists())