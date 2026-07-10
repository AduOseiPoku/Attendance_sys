from django.core.management.base import BaseCommand
from django.utils import timezone
from attendance.models import Member
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Archiving completed/graduated students from student churches (soft delete: set is_active=False)"

    def handle(self, *args, **options):
        today = timezone.now().date()
        logger.info("archive_completed_students: Command started.")

        # Find active members whose church is a student church and whose graduation cohort has passed
        completed_members = Member.objects.filter(
            church__is_student_church=True,
            is_active=True,
            graduation_year__completion_date__lte=today
        )
        
        count = completed_members.count()
        
        if count > 0:
            # Perform a bulk update to set is_active=False
            completed_members.update(is_active=False)
            logger.info(f"archive_completed_students: Archived {count} graduated student(s).")
            self.stdout.write(
                self.style.SUCCESS(f"Successfully archived {count} graduated student(s).")
            )
        else:
            logger.info("archive_completed_students: No graduated students to archive today.")
            self.stdout.write(
                self.style.SUCCESS("No graduated students to archive today.")
            )

