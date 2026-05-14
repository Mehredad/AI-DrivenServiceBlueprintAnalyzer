"""Shared rate-limiter instance — imported by main.py and all routers."""
import os
from slowapi import Limiter
from slowapi.util import get_remote_address

# Disable rate limiting in test environment so pytest suites don't hit limits
_enabled = os.getenv("ENVIRONMENT") != "test"
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"],
    enabled=_enabled,
)
