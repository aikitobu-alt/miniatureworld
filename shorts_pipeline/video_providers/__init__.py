"""AI video / scene providers."""

from .base import SceneProvider
from .kling import KlingProvider
from .runway import RunwayProvider
from .stills import StillsProvider

__all__ = ["SceneProvider", "KlingProvider", "RunwayProvider", "StillsProvider"]


def get_provider(name: str) -> SceneProvider:
    name = name.lower()
    if name == "kling":
        return KlingProvider()
    if name == "runway":
        return RunwayProvider()
    if name == "stills":
        return StillsProvider()
    raise ValueError(f"Unknown video provider: {name}")
