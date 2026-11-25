import os
import subprocess
import tarfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.backups import DUMP_SUFFIX, MEDIA_SUFFIX, backup_stem, stale_backups


class Command(BaseCommand):
    help = "Back up the database and media, keeping the newest backups."

    def add_arguments(self, parser):
        parser.add_argument("--dir", type=Path, default=settings.BACKUP_DIR)
        parser.add_argument("--keep", type=int, default=14)

    def handle(self, *args, **options):
        directory = options["dir"]
        directory.mkdir(parents=True, exist_ok=True)
        stem = backup_stem(timezone.now())
        dump = directory / f"{stem}{DUMP_SUFFIX}"
        media = directory / f"{stem}{MEDIA_SUFFIX}"
        partials = [
            dump.with_name(dump.name + ".partial"),
            media.with_name(media.name + ".partial"),
        ]
        try:
            subprocess.run(
                [
                    "pg_dump",
                    "--format=custom",
                    "--no-owner",
                    "--no-privileges",
                    f"--file={partials[0]}",
                    f"--dbname={os.environ['DATABASE_URL']}",
                ],
                check=True,
            )
            partials[0].rename(dump)
            with tarfile.open(partials[1], "w:gz") as tar:
                media_root = Path(settings.MEDIA_ROOT)
                if media_root.exists():
                    tar.add(media_root, arcname=media_root.name)
            partials[1].rename(media)
        except BaseException:
            for path in [*partials, dump, media]:
                path.unlink(missing_ok=True)
            raise
        stale = stale_backups([p.name for p in directory.iterdir()], options["keep"])
        for name in stale:
            (directory / name).unlink()
        self.stdout.write(f"Backed up to {stem}; removed {len(stale)} old file(s).")
