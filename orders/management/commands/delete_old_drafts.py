from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.drafts import delete_old_drafts


class Command(BaseCommand):
    help = "Delete draft orders older than a day."

    def handle(self, *args, **options):
        n = delete_old_drafts(timezone.now())
        self.stdout.write(f"Deleted {n} draft order(s).")
