import importlib.util
import socket

from .base import *

# Debug Toolbar & Extensions in Development
if importlib.util.find_spec("debug_toolbar") and importlib.util.find_spec("django_extensions"):
    INSTALLED_APPS += [
        "debug_toolbar",
        "django_extensions",
    ]
    # Insert DebugToolbarMiddleware as early as possible
    MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE

# Docker-safe INTERNAL_IPS mapping
try:
    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS = [ip[:-1] + "1" for ip in ips] + ["127.0.0.1", "10.0.2.2"]
except Exception:
    INTERNAL_IPS = ["127.0.0.1"]