from __future__ import annotations

import os
from typing import Protocol


class AIProvider(Protocol):
    name: str
    def review(self, prompt: str, context: dict) -> dict: ...


def configured_provider(provider_name: str | None = None) -> AIProvider | None:
    """Provider abstraction placeholder: no provider is hardcoded for MVP scaffold."""
    if not os.getenv("ATLAS_AI_API_KEY"):
        return None
    return None
