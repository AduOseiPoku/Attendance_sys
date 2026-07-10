import random
from datetime import date, time, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from attendance.models import Church, Member, Event, AttendanceLog, GraduationYear

FIRST_NAMES = [
    "John", "Jane", "Kofi", "Ama", "Kwame", "Yaw", "Adwoa", "Abena", "Kwaku", "Yaa",
    "Michael", "Sarah", "David", "Emmanuel", "Grace", "Samuel", "Elizabeth", "Daniel", "Rebecca", "Joseph",
    "Mary", "James", "Patricia", "Robert", "Jennifer", "William", "Linda", "Richard", "Barbara", "Thomas"
]

LAST_NAMES = [
    "Mensah", "Osei", "Appiah", "Agyei", "Adu", "Asare", "Boakye", "Koomson", "Gyamfi", "Owusu",
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Wilson", "Anderson", "Thomas", "Taylor", "Moore"
]

DEPARTMENTS = ["Choir", "Youth", "Ushering", "Media", "Sunday School", None]

ADDRESSES = [
    "Accra, Ghana", "Kumasi, Ghana", "East Legon", "Spintex Road", "Dansoman", "Madina", "Adenta"
]


class Command(BaseCommand):
    help = "Seeds a student church with 300 members (distributed across cohorts) and creates 5 events."

    def handle(self, *args, **options):
        # 1. Fetch or create a student church
        church, created = Church.objects.get_or_create(
            name="Campus Student Fellowship",
            defaults={"is_student_church": True}
        )
        if not church.is_student_church:
            church.is_student_church = True
            church.save()

        self.stdout.write(self.style.SUCCESS(f"Target student church: {church.name}"))

        # 2. Create cohorts (Year 1, Year 2, Year 3)
        today = timezone.now().date()
        cohorts = [
            GraduationYear.objects.get_or_create(
                church=church, year="Year 1",
                defaults={"completion_date": today + timedelta(days=365*3)}
            )[0],
            GraduationYear.objects.get_or_create(
                church=church, year="Year 2",
                defaults={"completion_date": today + timedelta(days=365*2)}
            )[0],
            # Completed cohort (yesterday)
            GraduationYear.objects.get_or_create(
                church=church, year="Year 3 (Graduated)",
                defaults={"completion_date": today - timedelta(days=1)}
            )[0]
        ]

        self.stdout.write(self.style.SUCCESS("Ensured graduation cohorts exist."))

        # 3. Create 300 members
        existing_phones = set(Member.objects.filter(church=church).values_list("phone_number", flat=True))
        members_to_create = []
        created_count = 0
        target_count = 300

        with transaction.atomic():
            while created_count < target_count:
                first = random.choice(FIRST_NAMES)
                last = random.choice(LAST_NAMES)
                name = f"{first} {last}"
                phone = f"23327{random.randint(1000000, 9999999)}"
                emergency = f"23320{random.randint(1000000, 9999999)}"

                if phone in existing_phones:
                    continue

                existing_phones.add(phone)
                address = random.choice(ADDRESSES)
                department = random.choice(DEPARTMENTS)
                cohort = random.choice(cohorts)

                members_to_create.append(
                    Member(
                        church=church,
                        name=name,
                        phone_number=phone,
                        emergency_phone_number=emergency,
                        address=address,
                        department=department,
                        graduation_year=cohort,
                        is_active=True
                    )
                )
                created_count += 1

            Member.objects.bulk_create(members_to_create)

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {created_count} members."))

        # 4. Create 5 events and log check-ins
        all_members = list(Member.objects.filter(church=church))
        
        for i in range(1, 6):
            event_date = today - timedelta(days=7 * (5 - i))
            event, event_created = Event.objects.get_or_create(
                church=church,
                name=f"Campus Fellowship - Week {i}",
                defaults={
                    "event_date": event_date,
                    "event_time": time(18, 0),
                    "is_active": True,
                    "description": f"Weekly student fellowship gathering - week {i}."
                }
            )

            # Check-in a subset of members (e.g. 70% to 90% attendance)
            random.shuffle(all_members)
            checkin_count = int(len(all_members) * random.uniform(0.70, 0.90))
            members_to_checkin = all_members[:checkin_count]

            existing_log_member_ids = set(
                AttendanceLog.objects.filter(event=event).values_list("member_id", flat=True)
            )

            logs_to_create = [
                AttendanceLog(church=church, member=m, event=event)
                for m in members_to_checkin
                if m.id not in existing_log_member_ids
            ]

            if logs_to_create:
                with transaction.atomic():
                    AttendanceLog.objects.bulk_create(logs_to_create)
                self.stdout.write(self.style.SUCCESS(f"Checked in {len(logs_to_create)} members for event '{event.name}'"))

        self.stdout.write(self.style.SUCCESS("Database seeding complete!"))
