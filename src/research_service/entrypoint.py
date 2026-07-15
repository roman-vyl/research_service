"""Console entrypoint."""

from __future__ import annotations

import uvicorn

from research_service.runtime.settings import Settings


def main() -> None:
    settings = Settings()
    uvicorn.run(
        "research_service.api.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
    )
