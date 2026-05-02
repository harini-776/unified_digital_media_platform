import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("trustmedia.audit")


def audit(
    action: str,
    *,
    user_id: Any = None,
    target_type: str | None = None,
    target_id: Any = None,
    **extra: Any,
) -> None:
    """Emit a structured audit log line to stdout.

    Never raises. An audit-write failure must never fail the underlying request.
    """
    try:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "user_id": str(user_id) if user_id is not None else None,
            "target_type": target_type,
            "target_id": str(target_id) if target_id is not None else None,
        }
        for k, v in extra.items():
            record[k] = str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
        logger.info(json.dumps(record))
    except Exception:
        pass
