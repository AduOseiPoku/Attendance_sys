"""
Management command: create_church_owner
Usage: python manage.py create_church_owner

Interactively creates a Django User + linked ChurchOwner record
so the church pastor gets a dedicated login account.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from attendance.models import ChurchOwner


class Command(BaseCommand):
    help = "Create a dedicated Church Owner account for the pastor/administrator."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Create Church Owner Account ===\n"))

        username = input("Enter username for the owner account: ").strip()
        if not username:
            self.stderr.write(self.style.ERROR("Username cannot be empty."))
            return

        if User.objects.filter(username=username).exists():
            self.stderr.write(self.style.ERROR(f"A user with username '{username}' already exists."))
            return

        email = input("Enter email address (optional, press Enter to skip): ").strip()

        import getpass
        password = getpass.getpass("Enter password: ")
        password_confirm = getpass.getpass("Confirm password: ")

        if password != password_confirm:
            self.stderr.write(self.style.ERROR("Passwords do not match."))
            return

        if len(password) < 8:
            self.stderr.write(self.style.ERROR("Password must be at least 8 characters."))
            return

        church_name = input("Enter the church name (e.g. 'Grace Chapel'): ").strip()
        if not church_name:
            church_name = "My Church"

        # Create the User (NOT a superuser)
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            is_staff=False,
            is_superuser=False,
        )

        # Create the linked ChurchOwner profile
        ChurchOwner.objects.create(user=user, church_name=church_name)

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Owner account created!\n"
                f"   Username    : {username}\n"
                f"   Church Name : {church_name}\n"
                f"   Login at    : /owner/login/\n"
            )
        )
