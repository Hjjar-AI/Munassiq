from django.core.management.base import BaseCommand
from catalog.maintenance import run_jobs


class Command(BaseCommand):
    help = 'Archive occurrences, expire reconfirmations, promote waitlists and purge three-day deletions.'

    def handle(self, *args, **options):
        self.stdout.write(f'Content jobs finished; processed: {run_jobs()}')
