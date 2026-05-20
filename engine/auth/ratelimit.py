"""In-memory login rate limiter — brute-force protection for /auth/login.

A single-process engine, so an in-process counter is sufficient. After
`login_max_attempts` consecutive failures a key (username) is locked out for
`login_lockout_minutes`. A successful login clears the counter.
"""

import time

from config import settings

# key -> (failure_count, locked_until_epoch)
_attempts: dict[str, tuple[int, float]] = {}


def is_locked(key: str) -> float:
    """Return seconds remaining on a lockout, or 0.0 if not locked."""
    entry = _attempts.get(key)
    if not entry:
        return 0.0
    _, locked_until = entry
    remaining = locked_until - time.time()
    return remaining if remaining > 0 else 0.0


def record_failure(key: str) -> None:
    count = _attempts.get(key, (0, 0.0))[0] + 1
    locked_until = 0.0
    if count >= settings.login_max_attempts:
        locked_until = time.time() + settings.login_lockout_minutes * 60
    _attempts[key] = (count, locked_until)


def reset(key: str) -> None:
    _attempts.pop(key, None)
