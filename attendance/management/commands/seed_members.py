import random
from datetime import date, time
from django.core.management.base import BaseCommand
from django.db import transaction
from attendance.models import Church, Member, Event, AttendanceLog

FIRST_NAMES = [
    "John", "Jane", "Kofi", "Ama", "Kwame", "Yaw", "Adwoa", "Abena", "Kwaku", "Yaa",
    "Michael", "Sarah", "David", "Emmanuel", "Grace", "Samuel", "Elizabeth", "Daniel", "Rebecca", "Joseph",
    "Mary", "James", "Patricia", "Robert", "Jennifer", "William", "Linda", "Richard", "Barbara", "Thomas",
    "Susan", "Charles", "Jessica", "Christopher", "Margaret", "Matthew", "Karen", "Patricia", "Joshua", "Emily",
    "Prince", "Blessing", "Joy", "Patience", "Hope", "Goodwill", "Bright", "Justice", "Precious", "Mercy"
]

LAST_NAMES = [
    "Mensah", "Osei", "Appiah", "Agyei", "Adu", "Asare", "Boakye", "Koomson", "Gyamfi", "Owusu",
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
    "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson"
]

DEPARTMENTS = ["Choir", "Youth", "Ushering", "Media", "Sunday School", "Men's Fellowship", "Women's Fellowship", None]

ADDRESSES = [
    "Accra, Ghana", "Kumasi, Ghana", "East Legon", "Tema Community 6", "Spintex Road",
    "Dansoman", "Madina", "Adenta", "Cantonments", "Airport Residential Area",
    "Osu", "Kasoa", "Lapaz", "Achimota", "Dome"
]

class Command(BaseCommand):
    help = "Generates mock members and attendance logs for testing database scale and visualization charts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=300,
            help="Number of mock members to generate."
        )
        parser.add_argument(
            "--church",
            type=str,
            help="Name of the church to generate members for (uses first church if unspecified)."
        )

    def handle(self, *args, **options):
        count = options["count"]
        church_name = options["church"]

        # 1. Fetch or create the church
        if church_name:
            church, created = Church.objects.get_or_create(name=church_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created new church: {church.name}"))
        else:
            church = Church.objects.first()
            if not church:
                church = Church.objects.create(name="Default Test Church")
                self.stdout.write(self.style.SUCCESS(f"Created default church: {church.name}"))
            else:
                self.stdout.write(self.style.NOTICE(f"Using existing church: {church.name}"))

        self.stdout.write(self.style.WARNING(f"Generating {count} mock members for {church.name}..."))

        # 2. Query existing phone numbers for uniqueness check
        existing_phones = set(Member.objects.filter(church=church).values_list("phone_number", flat=True))

        members_to_create = []
        created_count = 0

        # Generate unique records inside a transaction for performance
        with transaction.atomic():
            while created_count < count:
                first = random.choice(FIRST_NAMES)
                last = random.choice(LAST_NAMES)
                full_name = f"{first} {last}"
                
                # Generate standard phone number
                phone = f"23324{random.randint(1000000, 9999999)}"
                emergency_phone = f"23320{random.randint(1000000, 9999999)}"
                
                if phone in existing_phones:
                    continue  # Ensure we respect the unique constraint per church
                
                existing_phones.add(phone)
                address = random.choice(ADDRESSES)
                department = random.choice(DEPARTMENTS)
                
                members_to_create.append(
                    Member(
                        church=church,
                        name=full_name,
                        phone_number=phone,
                        emergency_phone_number=emergency_phone,
                        address=address,
                        department=department
                    )
                )
                created_count += 1

            # Bulk create to save database hits
            Member.objects.bulk_create(members_to_create)

        self.stdout.write(self.style.SUCCESS(f"Successfully created {created_count} members!"))

        # 3. Create a test event and check in a subset of the members to see chart visualization
        event, event_created = Event.objects.get_or_create(
            church=church,
            name="Mega Sunday Service",
            defaults={
                "event_date": date.today(),
                "event_time": time(9, 0),
                "is_active": True,
                "description": "Mock event populated with test members."
            }
        )
        if event_created:
            self.stdout.write(self.style.SUCCESS(f"Created a test event: {event.name}"))
        else:
            self.stdout.write(self.style.NOTICE(f"Using existing event: {event.name}"))
        
        # Load members from DB to get their primary keys
        all_members = list(Member.objects.filter(church=church))
        
        # Check in a random subset of members (65% to 85%)
        random.shuffle(all_members)
        checkin_pct = random.uniform(0.65, 0.85)
        checkin_count = int(len(all_members) * checkin_pct)
        members_to_checkin = all_members[:checkin_count]
        
        existing_log_member_ids = set(
            AttendanceLog.objects.filter(event=event).values_list("member_id", flat=True)
        )
        
        attendance_logs_to_create = []
        for m in members_to_checkin:
            if m.id not in existing_log_member_ids:
                attendance_logs_to_create.append(
                    AttendanceLog(church=church, member=m, event=event)
                )
                
        if attendance_logs_to_create:
            with transaction.atomic():
                AttendanceLog.objects.bulk_create(attendance_logs_to_create)
            self.stdout.write(self.style.SUCCESS(
                f"Successfully checked in {len(attendance_logs_to_create)} members to '{event.name}'."
            ))
        else:
            self.stdout.write(self.style.NOTICE("No new attendance logs required to check in."))
