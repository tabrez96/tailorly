import functools
import hashlib
from collections.abc import Iterable
from pathlib import Path

from django.conf import settings


def version_of(root: Path, paths: Iterable[Path]) -> str:
    """Short hash of the given files' names and bytes, independent of order."""
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


@functools.cache
def asset_version() -> str:
    """The release's version when set, else a hash of the static files.

    Computed once per process; a deploy restarts the workers.
    """
    if settings.ASSET_VERSION:
        return settings.ASSET_VERSION
    root = Path(settings.STATICFILES_DIRS[0])
    return version_of(
        root,
        [*root.glob("css/*.css"), *root.glob("js/*.js"), *root.glob("vendor/*.js")],
    )
