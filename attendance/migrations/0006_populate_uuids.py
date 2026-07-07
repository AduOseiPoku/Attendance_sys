import uuid
from django.db import migrations

def gen_uuid(apps, schema_editor):
    Church = apps.get_model('attendance', 'Church')
    for row in Church.objects.all():
        row.uuid = uuid.uuid4()
        row.save(update_fields=['uuid'])

    Member = apps.get_model('attendance', 'Member')
    for row in Member.objects.all():
        row.uuid = uuid.uuid4()
        row.save(update_fields=['uuid'])

    Event = apps.get_model('attendance', 'Event')
    for row in Event.objects.all():
        row.uuid = uuid.uuid4()
        row.save(update_fields=['uuid'])

class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0005_church_uuid_event_uuid_member_uuid'),
    ]

    operations = [
        migrations.RunPython(gen_uuid, elidable=True),
    ]
