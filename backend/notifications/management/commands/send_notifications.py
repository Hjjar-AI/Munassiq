from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from notifications.fcm import Sender
from notifications.worker import run


class Command(BaseCommand):
    help = 'Generate due reminders/digests and process a bounded batch of FCM notifications.'

    def handle(self, *args, **options):
        if not settings.FCM_ENABLED:
            raise CommandError('FCM is disabled. Configure Firebase before enabling delivery.')
        try:
            sender = Sender()
        except Exception:
            raise CommandError('Cannot initialize FCM. Check the private service-account file and dependencies.') from None
        self.stdout.write(f'Notification queue processed: {run(sender)}. Provider acceptance is not proof of device delivery.')
