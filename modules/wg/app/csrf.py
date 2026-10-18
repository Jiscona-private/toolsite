from __future__ import annotations

import hashlib
import hmac

from app.config import settings

# Split out of app/auth.py so app/templating.py (which needs this to put
# the token in every page) can import it without a circular import with
# auth.py (which imports `templates` from app/templating.py).


def csrf_token(cookie_version: int, member_id: int) -> str:
    message = f"{cookie_version}:{member_id}".encode()
    return hmac.new(settings.secret_key.encode(), message, hashlib.sha256).hexdigest()


def csrf_token_matches(token: str | None, cookie_version: int, member_id: int) -> bool:
    if not token:
        return False
    return hmac.compare_digest(token, csrf_token(cookie_version, member_id))
