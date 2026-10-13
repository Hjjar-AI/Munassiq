"""File-backed SQLite test database supports real multi-connection race tests."""
from copy import deepcopy
from .settings import *  # noqa: F403

DATABASES = deepcopy(DATABASES)
DATABASES['default']['TEST'] = {'NAME': str(RUNTIME_ROOT / 'test.sqlite3')}
