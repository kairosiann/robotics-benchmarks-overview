"""
Abstract saver interface for replay/conversion scripts.

This keeps shared lifecycle and resume boilerplate in one place so concrete savers
only implement format-specific logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from typing_extensions import Self


class EpisodeSaver(ABC):
    """Common interface for writing episodes in different dataset formats."""

    def __init__(self) -> None:
        self._existing_demos: set[str] = set()

    @property
    def existing_demos(self) -> set[str]:
        """Episode keys already present in the output destination."""
        return set(self._existing_demos)

    @property
    @abstractmethod
    def destination(self) -> str:
        """Human-readable destination string for logs."""

    @abstractmethod
    def open(self) -> None:
        """Open the destination and populate resume metadata."""

    @abstractmethod
    def close(self) -> None:
        """Close and clean up any destination resources."""

    @abstractmethod
    def write_episode(
        self,
        *,
        episode_key: str,
        trajectory: dict[str, Any],
        initial_state: dict[str, Any],
        task: str,
    ) -> None:
        """Write one episode to the destination format."""

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
