from datetime import date, time
from urllib.parse import quote, urlencode

from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import AttendanceLog, Event, Member, Church, ChurchOwner

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
        church = Church.objects.create(name="Test Church Legacy Unique")
        Member.objects.create(
            church=church,
            name="First User",
            phone_number="+233500000020",
            emergency_phone_number="+233500000120",
            address="Address 1",
        )
        with self.assertRaises(IntegrityError):
            Member.objects.create(
                church=church,
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


# ===========================================================================
# Owner Dashboard Tests
# ===========================================================================
from django.contrib.auth.models import User
from .models import ChurchOwner

# In-memory templates for the owner dashboard screens
OWNER_TEMPLATES = {
    **LOC_MEM_TEMPLATES,
    "owner/login.html":        "<html>login{% if error %} error:{{ error }}{% endif %}</html>",
    "owner/dashboard.html":    "<html>dashboard members={{ total_members }} events={{ total_events }} checkins={{ total_checkins }} rate={{ avg_rate }}</html>",
    "owner/members.html":      "<html>members count={{ members|length }}</html>",
    "owner/event_detail.html": "<html>present={{ present_count }} absent={{ absent_count }} pct={{ attendance_pct }}</html>",
}


def make_owner(username="pastor", password="TestPass123", church_name="Test Church"):
    """Helper: create a User + linked ChurchOwner and return both."""
    user  = User.objects.create_user(username=username, password=password)
    owner = ChurchOwner.objects.create(user=user, church_name=church_name)
    return user, owner


def make_member(name, phone, department=None):
    """Helper: create a minimal Member."""
    return Member.objects.create(
        name=name,
        phone_number=phone,
        emergency_phone_number="000",
        address="Test Address",
        department=department,
    )


def make_event(name="Sunday Service", days_offset=0):
    """Helper: create an Event relative to today."""
    from datetime import date, timedelta, time as dtime
    d = date.today() + timedelta(days=days_offset)
    return Event.objects.create(name=name, event_date=d, event_time=dtime(9, 0))


# ---------------------------------------------------------------------------
# 1. ChurchOwner model
# ---------------------------------------------------------------------------
class ChurchOwnerModelTests(TestCase):

    def test_str_representation(self):
        user, owner = make_owner()
        self.assertEqual(str(owner), "Owner: pastor (Test Church)")

    def test_owner_linked_to_user(self):
        user, owner = make_owner()
        self.assertEqual(owner.user, user)
        self.assertEqual(user.church_owner, owner)

    def test_cascade_delete_user_removes_owner(self):
        user, _ = make_owner()
        user.delete()
        self.assertEqual(ChurchOwner.objects.count(), 0)

    def test_default_church_name(self):
        user = User.objects.create_user(username="defaultpastor", password="Pass1234")
        owner = ChurchOwner.objects.create(user=user)
        self.assertEqual(owner.church_name, "My Church")

    def test_one_user_cannot_have_two_church_owners(self):
        from django.db import IntegrityError
        user, _ = make_owner()
        with self.assertRaises(IntegrityError):
            ChurchOwner.objects.create(user=user, church_name="Duplicate")


# ---------------------------------------------------------------------------
# 2. @owner_required decorator
# ---------------------------------------------------------------------------
@override_settings(TEMPLATES=[{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [], "APP_DIRS": False,
    "OPTIONS": {
        "loaders": [("django.template.loaders.locmem.Loader", OWNER_TEMPLATES)],
        "context_processors": [
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ],
    },
}])
class OwnerRequiredDecoratorTests(TestCase):

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get(reverse("owner_dashboard"))
        self.assertRedirects(response, reverse("owner_login"), fetch_redirect_response=False)

    def test_superuser_without_church_owner_is_redirected(self):
        """A superuser who has no ChurchOwner profile cannot access the dashboard."""
        User.objects.create_superuser("su", "su@test.com", "SuperPass1")
        self.client.login(username="su", password="SuperPass1")
        response = self.client.get(reverse("owner_dashboard"))
        self.assertRedirects(response, reverse("owner_login"), fetch_redirect_response=False)

    def test_owner_can_access_dashboard(self):
        make_owner()
        self.client.login(username="pastor", password="TestPass123")
        response = self.client.get(reverse("owner_dashboard"))
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# 3. Login / Logout views
# ---------------------------------------------------------------------------
@override_settings(TEMPLATES=[{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [], "APP_DIRS": False,
    "OPTIONS": {
        "loaders": [("django.template.loaders.locmem.Loader", OWNER_TEMPLATES)],
        "context_processors": [
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ],
    },
}])
class OwnerLoginLogoutTests(TestCase):

    def setUp(self):
        self.user, self.owner = make_owner()

    def test_login_page_get(self):
        response = self.client.get(reverse("owner_login"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "owner/login.html")

    def test_already_logged_in_redirects_to_dashboard(self):
        self.client.login(username="pastor", password="TestPass123")
        response = self.client.get(reverse("owner_login"))
        self.assertRedirects(response, reverse("owner_dashboard"), fetch_redirect_response=False)

    def test_valid_login_redirects_to_dashboard(self):
        response = self.client.post(reverse("owner_login"), {
            "username": "pastor", "password": "TestPass123"
        })
        self.assertRedirects(response, reverse("owner_dashboard"), fetch_redirect_response=False)

    def test_wrong_password_returns_error(self):
        response = self.client.post(reverse("owner_login"), {
            "username": "pastor", "password": "WrongPassword"
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "error")

    def test_superuser_without_church_owner_cannot_login(self):
        """A plain superuser (no ChurchOwner profile) must be rejected."""
        User.objects.create_superuser("su2", "su2@test.com", "SuperPass2")
        response = self.client.post(reverse("owner_login"), {
            "username": "su2", "password": "SuperPass2"
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "error")

    def test_logout_clears_session_and_redirects(self):
        self.client.login(username="pastor", password="TestPass123")
        response = self.client.get(reverse("owner_logout"))
        self.assertRedirects(response, reverse("owner_login"), fetch_redirect_response=False)
        # After logout, accessing dashboard should redirect to login
        dashboard = self.client.get(reverse("owner_dashboard"))
        self.assertRedirects(dashboard, reverse("owner_login"), fetch_redirect_response=False)


# ---------------------------------------------------------------------------
# 4. Dashboard view — stat cards & chart data
# ---------------------------------------------------------------------------
@override_settings(TEMPLATES=[{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [], "APP_DIRS": False,
    "OPTIONS": {
        "loaders": [("django.template.loaders.locmem.Loader", OWNER_TEMPLATES)],
        "context_processors": [
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ],
    },
}])
class OwnerDashboardViewTests(TestCase):

    def setUp(self):
        self.user, self.owner = make_owner()
        self.client.login(username="pastor", password="TestPass123")

        self.member1 = make_member("Alice", "111")
        self.member2 = make_member("Bob",   "222")
        self.event1  = make_event("Service A", days_offset=-7)
        self.event2  = make_event("Service B", days_offset=0)

        AttendanceLog.objects.create(member=self.member1, event=self.event1)
        AttendanceLog.objects.create(member=self.member2, event=self.event1)
        AttendanceLog.objects.create(member=self.member1, event=self.event2)

    def test_dashboard_returns_200(self):
        response = self.client.get(reverse("owner_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_stat_cards_correct(self):
        response = self.client.get(reverse("owner_dashboard"))
        self.assertEqual(response.context["total_members"],  2)
        self.assertEqual(response.context["total_events"],   2)
        self.assertEqual(response.context["total_checkins"], 3)

    def test_avg_rate_calculation(self):
        # 3 check-ins out of 2 members × 2 events = 4 possible → 75%
        response = self.client.get(reverse("owner_dashboard"))
        self.assertEqual(response.context["avg_rate"], 75.0)

    def test_avg_rate_zero_when_no_events(self):
        Event.objects.all().delete()
        AttendanceLog.objects.all().delete()
        response = self.client.get(reverse("owner_dashboard"))
        self.assertEqual(response.context["avg_rate"], 0)

    def test_chart_labels_and_data_present(self):
        response = self.client.get(reverse("owner_dashboard"))
        import json
        labels = json.loads(response.context["chart_labels"])
        data   = json.loads(response.context["chart_data"])
        self.assertEqual(len(labels), 2)
        self.assertEqual(len(data),   2)

    def test_chart_data_ordered_chronologically(self):
        response = self.client.get(reverse("owner_dashboard"))
        import json
        data = json.loads(response.context["chart_data"])
        # event1 (7 days ago) had 2 attendees, event2 (today) had 1
        self.assertEqual(data[0], 2)
        self.assertEqual(data[1], 1)

    def test_recent_events_limited_to_5(self):
        for i in range(6):
            make_event(f"Extra Service {i}", days_offset=-i - 1)
        response = self.client.get(reverse("owner_dashboard"))
        self.assertLessEqual(len(list(response.context["recent_events"])), 5)


# ---------------------------------------------------------------------------
# 5. Members view — search & department filter
# ---------------------------------------------------------------------------
@override_settings(TEMPLATES=[{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [], "APP_DIRS": False,
    "OPTIONS": {
        "loaders": [("django.template.loaders.locmem.Loader", OWNER_TEMPLATES)],
        "context_processors": [
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ],
    },
}])
class OwnerMembersViewTests(TestCase):

    def setUp(self):
        self.user, _ = make_owner()
        self.client.login(username="pastor", password="TestPass123")

        self.alice = make_member("Alice Mensah", "333", department="Choir")
        self.bob   = make_member("Bob Asante",   "444", department="Ushers")
        self.carol = make_member("Carol Osei",   "555", department="Choir")

        event = make_event()
        AttendanceLog.objects.create(member=self.alice, event=event)
        AttendanceLog.objects.create(member=self.alice, event=make_event("Second", 1))

    def test_members_page_returns_200(self):
        response = self.client.get(reverse("owner_members"))
        self.assertEqual(response.status_code, 200)

    def test_all_members_shown_by_default(self):
        response = self.client.get(reverse("owner_members"))
        self.assertEqual(response.context["members"].count(), 3)

    def test_search_by_name(self):
        response = self.client.get(reverse("owner_members") + "?search=alice")
        members = list(response.context["members"])
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0].name, "Alice Mensah")

    def test_search_by_phone(self):
        response = self.client.get(reverse("owner_members") + "?search=444")
        members = list(response.context["members"])
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0].name, "Bob Asante")

    def test_search_no_match_returns_empty(self):
        response = self.client.get(reverse("owner_members") + "?search=zzz")
        self.assertEqual(response.context["members"].count(), 0)

    def test_department_filter(self):
        response = self.client.get(reverse("owner_members") + "?department=Choir")
        names = [m.name for m in response.context["members"]]
        self.assertIn("Alice Mensah", names)
        self.assertIn("Carol Osei",   names)
        self.assertNotIn("Bob Asante", names)

    def test_department_dropdown_contains_distinct_values(self):
        response = self.client.get(reverse("owner_members"))
        depts = list(response.context["departments"])
        self.assertIn("Choir",  depts)
        self.assertIn("Ushers", depts)
        self.assertEqual(len(depts), 2)  # no duplicates

    def test_members_sorted_by_attendance_descending(self):
        """Alice has 2 check-ins; Bob and Carol have 0 — Alice should be first."""
        response = self.client.get(reverse("owner_members"))
        members = list(response.context["members"])
        self.assertEqual(members[0].name, "Alice Mensah")

    def test_combined_search_and_department_filter(self):
        response = self.client.get(reverse("owner_members") + "?search=carol&department=Choir")
        members = list(response.context["members"])
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0].name, "Carol Osei")


# ---------------------------------------------------------------------------
# 6. Event Detail view — present / absent roster
# ---------------------------------------------------------------------------
@override_settings(TEMPLATES=[{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [], "APP_DIRS": False,
    "OPTIONS": {
        "loaders": [("django.template.loaders.locmem.Loader", OWNER_TEMPLATES)],
        "context_processors": [
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ],
    },
}])
class OwnerEventDetailViewTests(TestCase):

    def setUp(self):
        self.user, _ = make_owner()
        self.client.login(username="pastor", password="TestPass123")

        self.member1 = make_member("Present Person", "666")
        self.member2 = make_member("Absent Person",  "777")
        self.event   = make_event("Big Service")

        AttendanceLog.objects.create(member=self.member1, event=self.event)

    def test_event_detail_returns_200(self):
        response = self.client.get(reverse("owner_event_detail", kwargs={"pk": self.event.pk}))
        self.assertEqual(response.status_code, 200)

    def test_event_detail_404_for_missing_event(self):
        response = self.client.get(reverse("owner_event_detail", kwargs={"pk": 9999}))
        self.assertEqual(response.status_code, 404)

    def test_present_count_correct(self):
        response = self.client.get(reverse("owner_event_detail", kwargs={"pk": self.event.pk}))
        self.assertEqual(response.context["present_count"], 1)

    def test_absent_count_correct(self):
        response = self.client.get(reverse("owner_event_detail", kwargs={"pk": self.event.pk}))
        self.assertEqual(response.context["absent_count"], 1)

    def test_present_member_in_correct_list(self):
        response = self.client.get(reverse("owner_event_detail", kwargs={"pk": self.event.pk}))
        present_names = [m.name for m in response.context["present_members"]]
        self.assertIn("Present Person", present_names)
        self.assertNotIn("Absent Person", present_names)

    def test_absent_member_in_correct_list(self):
        response = self.client.get(reverse("owner_event_detail", kwargs={"pk": self.event.pk}))
        absent_names = [m.name for m in response.context["absent_members"]]
        self.assertIn("Absent Person", absent_names)
        self.assertNotIn("Present Person", absent_names)

    def test_attendance_percentage_correct(self):
        # 1 present out of 2 total members = 50%
        response = self.client.get(reverse("owner_event_detail", kwargs={"pk": self.event.pk}))
        self.assertEqual(response.context["attendance_pct"], 50.0)

    def test_attendance_pct_zero_when_no_members(self):
        Member.objects.all().delete()
        AttendanceLog.objects.all().delete()
        response = self.client.get(reverse("owner_event_detail", kwargs={"pk": self.event.pk}))
        self.assertEqual(response.context["attendance_pct"], 0)

    def test_unauthenticated_redirected_from_event_detail(self):
        self.client.logout()
        response = self.client.get(reverse("owner_event_detail", kwargs={"pk": self.event.pk}))
        self.assertRedirects(response, reverse("owner_login"), fetch_redirect_response=False)


# ---------------------------------------------------------------------------
# Multi-Tenancy / Church Isolation Tests
# ---------------------------------------------------------------------------
class MultiTenancyTests(TestCase):

    def setUp(self):
        # Create two churches
        self.church_a = Church.objects.create(name="Church A")
        self.church_b = Church.objects.create(name="Church B")

        # Create owners for both churches
        self.user_a = User.objects.create_user(username="pastor_a", password="Password123")
        self.owner_a = ChurchOwner.objects.create(user=self.user_a, church=self.church_a, church_name="Church A")

        self.user_b = User.objects.create_user(username="pastor_b", password="Password123")
        self.owner_b = ChurchOwner.objects.create(user=self.user_b, church=self.church_b, church_name="Church B")

    def test_phone_number_uniqueness_isolated_per_church(self):
        # Register same phone number in Church A
        member_a = Member.objects.create(
            church=self.church_a,
            name="John Doe",
            phone_number="233241234567",
            emergency_phone_number="000",
            address="Accra"
        )
        self.assertEqual(Member.objects.filter(phone_number="233241234567").count(), 1)

        # Register same phone number in Church B - should succeed
        member_b = Member.objects.create(
            church=self.church_b,
            name="John Doe",
            phone_number="233241234567",
            emergency_phone_number="000",
            address="Kumasi"
        )
        self.assertEqual(Member.objects.filter(phone_number="233241234567").count(), 2)

        # Registering same phone number in Church A again should raise IntegrityError
        with self.assertRaises(IntegrityError):
            Member.objects.create(
                church=self.church_a,
                name="Another John",
                phone_number="233241234567",
                emergency_phone_number="111",
                address="Accra"
            )

    @override_settings(TEMPLATES=[{
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [], "APP_DIRS": False,
        "OPTIONS": {
            "loaders": [("django.template.loaders.locmem.Loader", OWNER_TEMPLATES)],
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }])
    def test_church_data_isolation(self):
        # Create members for Church A and B
        member_a = Member.objects.create(
            church=self.church_a,
            name="Member A",
            phone_number="111",
            emergency_phone_number="000",
            address="Accra"
        )
        member_b = Member.objects.create(
            church=self.church_b,
            name="Member B",
            phone_number="222",
            emergency_phone_number="000",
            address="Accra"
        )

        # Create events for Church A and B
        event_a = Event.objects.create(
            church=self.church_a,
            name="Event A",
            event_date=date.today(),
            event_time=time(9, 0)
        )
        event_b = Event.objects.create(
            church=self.church_b,
            name="Event B",
            event_date=date.today(),
            event_time=time(9, 0)
        )

        # Login as Pastor A
        self.client.login(username="pastor_a", password="Password123")

        # Check dashboard metrics for Church A
        response = self.client.get(reverse("owner_dashboard"))
        self.assertEqual(response.context["total_members"], 1)
        self.assertEqual(response.context["total_events"], 1)

        # Check members list for Church A
        response = self.client.get(reverse("owner_members"))
        members = [m.name for m in response.context["members"]]
        self.assertIn("Member A", members)
        self.assertNotIn("Member B", members)

        # Check event detail for Church A event
        response = self.client.get(reverse("owner_event_detail", kwargs={"pk": event_a.pk}))
        self.assertEqual(response.status_code, 200)

        # Attempting to access Church B event should return 404
        response = self.client.get(reverse("owner_event_detail", kwargs={"pk": event_b.pk}))
        self.assertEqual(response.status_code, 404)