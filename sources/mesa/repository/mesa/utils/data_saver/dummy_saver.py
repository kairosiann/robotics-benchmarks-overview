"""
No-op saver used when replaying trajectories without writing outputs.
"""

from __future__ import annotations

from typing import Any

from mesa.utils.data_saver.base_saver import EpisodeSaver


class DummySaver(EpisodeSaver):
    """Saver implementation that intentionally performs no writes."""

    @property
    def destination(self) -> str:
        return "no output (data_format=None)"

    def open(self) -> None:
        self._existing_demos = set()

    def close(self) -> None:
        self._existing_demos = set()

    def write_episode(
        self,
        *,
        episode_key: str,
        trajectory: dict[str, Any],
        initial_state: dict[str, Any],
        task: str,
    ) -> None:
        pass
