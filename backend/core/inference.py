"""A database-wide, non-queueing inference budget shared by WSGI workers."""
from contextlib import contextmanager

from django.db import connections

LOCK_NAMESPACE = 1936748148
LOCK_SLOT = 1


class InferenceBusy(Exception):
    pass


@contextmanager
def inference_slot():
    # A separate short-lived connection keeps session locks out of pooled application connections.
    guard = connections["default"].copy()
    acquired = False
    try:
        guard.ensure_connection()
        with guard.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s, %s)", [LOCK_NAMESPACE, LOCK_SLOT])
            acquired = cursor.fetchone()[0]
        if not acquired:
            raise InferenceBusy("Local AI is busy. Retry after the current request finishes.")
        yield
    finally:
        try:
            if acquired:
                with guard.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_unlock(%s, %s)", [LOCK_NAMESPACE, LOCK_SLOT])
        finally:
            guard.close()
