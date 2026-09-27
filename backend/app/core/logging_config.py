from __future__ import annotations

import logging


def configure_dependency_logging() -> None:
    """Keep dependency logs from exposing signed URLs or provider request details."""

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

