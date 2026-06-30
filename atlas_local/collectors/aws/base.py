from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from botocore.exceptions import BotoCoreError, ClientError


READ_ONLY_NOTE = "collector uses describe/list/get APIs only and never mutates AWS"


class AwsCollector:
    service = "unknown"
    regional = True

    def collect(self, session: Any, region: str | None) -> dict[str, Any]:
        raise NotImplementedError

    def safe_call(self, call: Callable[[], Any], errors: list[str], label: str) -> Any:
        try:
            return call()
        except (ClientError, BotoCoreError, Exception) as exc:  # intentionally graceful for missing perms
            errors.append(f"{label}: {type(exc).__name__}: {exc}")
            return None

    def envelope(self, *, account_id: str | None, region: str | None, items: dict[str, Any], errors: list[str]) -> dict[str, Any]:
        return {
            "metadata": {
                "service": self.service,
                "collector": self.__class__.__name__,
                "account_id": account_id,
                "region": region,
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "read_only": True,
                "note": READ_ONLY_NOTE,
            },
            "items": items,
            "errors": errors,
        }
