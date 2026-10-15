from __future__ import annotations

from dataclasses import dataclass
from typing import assert_never

from docmorph.core.engine import Engine
from docmorph.core.errors import ConversionNotAvailable
from docmorph.core.models import Detection, Format, Mode, PdfKind, Route

# Explicit two-step chains: (source, target) -> intermediate format.
_CHAINS: dict[tuple[Format, Format], Format] = {
    (Format.PDF, Format.DOC): Format.DOCX,
}


@dataclass(frozen=True)
class Step:
    engine: Engine
    route: Route

    @property
    def mode(self) -> Mode:
        return self.route.mode


@dataclass(frozen=True)
class TargetOption:
    target: Format
    modes: tuple[Mode, ...]


def _mode_rank(mode: Mode) -> int:
    match mode:
        case Mode.STANDARD | Mode.LAYOUT:
            return 0
        case Mode.STRUCTURE:
            return 1
        case Mode.AUTO:
            return 2
        case _:
            assert_never(mode)


class Registry:
    def __init__(self, engines: list[Engine]) -> None:
        self._engines = engines
        self._unavailable: dict[str, str] = {}
        self._route_unavailable: dict[tuple[str, Route], str] = {}
        for engine in engines:
            reason = engine.availability()
            if reason is not None:
                self._unavailable[engine.name] = reason
                continue
            for route in engine.routes:
                if (route_reason := engine.route_availability(route)) is not None:
                    self._route_unavailable[(engine.name, route)] = route_reason

    @property
    def engines(self) -> list[Engine]:
        return list(self._engines)

    def unavailable_reason(self, engine: Engine) -> str | None:
        return self._unavailable.get(engine.name)

    def _reason(self, engine: Engine, route: Route) -> str | None:
        return self._unavailable.get(engine.name) or self._route_unavailable.get((engine.name, route))

    def _candidates(self, detection: Detection, target: Format, available: bool = True) -> list[Step]:
        steps = [
            Step(engine, route)
            for engine in self._engines
            for route in engine.routes
            if route.target == target
            and route.accepts(detection)
            and (self._reason(engine, route) is None) == available
        ]
        return sorted(steps, key=lambda s: _mode_rank(s.mode))

    def _plans(self, detection: Detection, target: Format) -> tuple[list[Step], list[Step]]:
        """Return (first-step candidates, fixed tail) for reaching `target`."""
        direct = self._candidates(detection, target)
        if direct:
            return direct, []
        via = _CHAINS.get((detection.format, target))
        if via is not None:
            first = self._candidates(detection, via)
            tail = self._candidates(Detection(format=via), target)
            if first and tail:
                return first, [tail[0]]
        return [], []

    def resolve(self, detection: Detection, target: Format, mode: Mode = Mode.AUTO) -> list[Step]:
        if detection.format == target:
            raise ConversionNotAvailable("Le fichier est déjà dans ce format.")
        first, tail = self._plans(detection, target)
        if not first:
            raise ConversionNotAvailable(self._why_not(detection, target))
        chosen = next((s for s in first if s.mode == mode), first[0])
        return [chosen, *tail]

    def options(self, detection: Detection) -> list[TargetOption]:
        result = []
        for target in Format:
            if target == detection.format:
                continue
            first, _ = self._plans(detection, target)
            if first:
                modes = tuple(dict.fromkeys(s.mode for s in first))
                result.append(TargetOption(target=target, modes=modes))
        return result

    def matrix(self) -> list[dict]:
        rows = []
        for fmt in Format:
            kinds: list[PdfKind | None] = list(PdfKind) if fmt == Format.PDF else [None]
            for kind in kinds:
                detection = Detection(format=fmt, pdf_kind=kind)
                for option in self.options(detection):
                    rows.append(
                        {
                            "source": fmt.value,
                            "pdf_kind": kind.value if kind else None,
                            "target": option.target.value,
                            "modes": [m.value for m in option.modes],
                        }
                    )
        return rows

    def _why_not(self, detection: Detection, target: Format) -> str:
        label = f"{detection.format.value.upper()} vers {target.value.upper()}"
        blocked = self._candidates(detection, target, available=False)
        via = _CHAINS.get((detection.format, target))
        if not blocked and via is not None:
            blocked = self._candidates(detection, via, available=False) or self._candidates(
                Detection(format=via), target, available=False
            )
        if blocked:
            step = blocked[0]
            return f"Conversion {label} indisponible : {step.engine.label} — {self._reason(step.engine, step.route)}"
        return f"Conversion {label} non prise en charge."
