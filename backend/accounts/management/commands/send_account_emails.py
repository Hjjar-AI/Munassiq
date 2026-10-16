from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from accounts.models import EmailMessage, MaintenanceRun


class Command(BaseCommand):
    help = 'Send up to 20 queued bilingual account emails; retry temporary failures without logging secrets.'

    def handle(self, *args, **options):
        if not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL:
            raise CommandError('Configure EMAIL_HOST and EMAIL_FROM first.')
        run = MaintenanceRun.objects.create(name='accounts.send_email')
        sent = 0
        for _ in range(20):
            # Single small queue; serialize senders so two workers cannot send the
            # same row concurrently. SMTP timeout bounds the transaction duration.
            with transaction.atomic():
                now = timezone.now()
                message = EmailMessage.objects.select_for_update().filter(sent_at=None, expires_at__gt=now,
                    next_attempt_at__lte=now, user__is_active=True).order_by('pk').first()
                if not message:
                    break
                try:
                    delivered = send_mail(message.subject, message.body, settings.DEFAULT_FROM_EMAIL, [message.recipient])
                    if delivered != 1:
                        raise OSError('Delivery not accepted')
                except Exception:
                    message.attempts += 1
                    message.next_attempt_at = now + timedelta(seconds=min(3600, 30 * 2 ** min(message.attempts, 7)))
                    message.save(update_fields=['attempts', 'next_attempt_at'])
                    self.stderr.write('Email deferred; retry scheduled. No address or token logged.')
                else:
                    message.sent_at = now
                    message.body = ''  # Do not retain delivered reset/verification secrets.
                    message.save(update_fields=['sent_at', 'body'])
                    sent += 1
        run.finished_at, run.processed = timezone.now(), sent
        run.save(update_fields=['finished_at', 'processed'])
        self.stdout.write(f'Accepted by SMTP: {sent}. Delivery to inbox is not guaranteed.')
