from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse
from urllib.parse import urljoin
from attendance.models import Event
import qrcode
import qrcode.image.svg
import os


class Command(BaseCommand):
    help = "Generate a QR asset linking to an event scan page."

    def add_arguments(self, parser):
        parser.add_argument('--event', type=int, required=True, help='Event id')
        parser.add_argument('--host', type=str, required=True, help='Host (e.g. http://192.168.1.100:8000)')
        parser.add_argument('--out', type=str, default=None, help='Output filename (png or svg)')
        parser.add_argument('--format', type=str, choices=['png', 'svg'], default='png')

    def handle(self, *args, **opts):
        event_id = opts['event']
        host = opts['host'].rstrip('/')
        out = opts['out']
        fmt = opts['format']

        try:
            event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            raise CommandError(f'Event with id {event_id} not found.')

        path = reverse('scan_landing', args=[event.id])
        full_url = urljoin(host + '/', path.lstrip('/'))

        if not out:
            out = f'live_event_{event_id}_barcode.{fmt}'

        # Ensure directory exists for output
        out_dir = os.path.dirname(out)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        if fmt == 'svg':
            factory = qrcode.image.svg.SvgImage
            img = qrcode.make(full_url, image_factory=factory)
            img.save(out)
        else:
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(full_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(out)

        self.stdout.write(self.style.SUCCESS(f'QR generated for event "{event.name}": {full_url} -> {out}'))
