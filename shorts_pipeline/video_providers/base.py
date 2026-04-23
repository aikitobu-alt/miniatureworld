"""SceneProvider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import Scene


class SceneProvider(ABC):
    name: str

    @abstractmethod
    def render(self, scene: Scene, out_path: Path) -> Path:
        """Generate an MP4 (9:16, silent) for this scene and return the path."""
        raise NotImplementedError
