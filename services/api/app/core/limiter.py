from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _user_or_ip_key(request: Request) -> str:
    """Rate-limit key: prefer the authed user_id, fall back to client IP.

    `request.state.user` is set by the auth middleware/dep when the request is
    authenticated. For unauthed requests we fall back to client IP.
    """
    user = getattr(request.state, "user", None)
    if user is not None and getattr(user, "id", None) is not None:
        return f"user:{user.id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_user_or_ip_key)
