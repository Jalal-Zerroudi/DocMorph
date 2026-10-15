from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from docmorph.core.models import Resource, Route


class Engine(ABC):
    name: ClassVar[str]
    label: ClassVar[str]
    resource: ClassVar[Resource] = Resource.CPU
    routes: ClassVar[tuple[Route, ...]]

    @abstractmethod
    def availability(self) -> str | None:
        """Return None when the engine can run on this machine, otherwise the reason (French)."""

    def route_availability(self, route: Route) -> str | None:
        """Like `availability`, for routes with extra requirements (e.g. OCR language packs)."""
        return None

    @abstractmethod
    def convert(self, src: Path, dst: Path, route: Route) -> None:
        """Convert `src` into `dst`. Raise a DocMorphError on failure."""
