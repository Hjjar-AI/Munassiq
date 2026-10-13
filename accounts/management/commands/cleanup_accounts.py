from django.core.management.base import BaseCommand
from accounts.maintenance import cleanup_accounts


class Command(BaseCommand):
    help = 'Delete accounts never verified within 7 days and expire auth records; safe to repeat.'

    def handle(self, *args, **options):
        count = cleanup_accounts()
        self.stdout.write(f'Account cleanup finished: {count} unverified accounts deleted.')
