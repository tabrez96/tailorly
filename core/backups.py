from collections.abc import Iterable
from datetime import datetime

from django.utils import timezone

PREFIX = "tailorly-"
DUMP_SUFFIX = ".dump"
MEDIA_SUFFIX = "-media.tar.gz"


def backup_stem(now: datetime) -> str:
    """'tailorly-2026-11-25-023000' in shop time; sorts by time as text."""
    return PREFIX + timezone.localtime(now).strftime("%Y-%m-%d-%H%M%S")


def stale_backups(names: Iterable[str], keep: int) -> list[str]:
    """File names belonging to all but the newest `keep` complete backups.

    Only stems with both a dump and a media archive count toward `keep`;
    orphan files are returned for removal.
    """
    if keep < 1:
        raise ValueError("keep must be at least 1")
    stems_by_name = {}
    suffixes_by_stem = {}
    for name in names:
        if not name.startswith(PREFIX):
            continue
        for suffix in (DUMP_SUFFIX, MEDIA_SUFFIX):
            if name.endswith(suffix):
                stem = name.removesuffix(suffix)
                stems_by_name[name] = stem
                suffixes_by_stem.setdefault(stem, set()).add(suffix)
    complete = [s for s, found in suffixes_by_stem.items() if len(found) == 2]
    kept = set(sorted(complete, reverse=True)[:keep])
    return sorted(n for n, stem in stems_by_name.items() if stem not in kept)
