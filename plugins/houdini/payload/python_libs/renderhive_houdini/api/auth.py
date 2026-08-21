"""Authentication helpers shared by API diagnostics and tests."""

from __future__ import absolute_import


def authentication_header(config):
    auth = (config or {}).get("auth") if isinstance((config or {}).get("auth"), dict) else {}
    token = str(auth.get("token") or "").strip()
    auth_type = str(auth.get("type") or "token").strip().lower()
    if not token or auth_type == "none":
        return {}
    if auth_type == "x-session-token":
        return {"X-Session-Token": token}
    return {"Authorization": "Token {}".format(token)}


def token_configured(config):
    return bool(str((((config or {}).get("auth") or {}).get("token")) or "").strip())
