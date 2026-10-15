from __future__ import annotations

from pathlib import Path

import pytest

from docmorph.core.engine import Engine
from docmorph.core.errors import ConversionNotAvailable
from docmorph.core.models import Detection, Format, Mode, PdfKind, Route
from docmorph.core.registry import Registry

DIGITAL = Detection(format=Format.PDF, pdf_kind=PdfKind.DIGITAL)
SCANNED = Detection(format=Format.PDF, pdf_kind=PdfKind.SCANNED)


class FakeEngine(Engine):
    def __init__(
        self,
        name: str,
        routes: tuple[Route, ...],
        reason: str | None = None,
        route_reasons: dict[Route, str] | None = None,
    ) -> None:
        self.name = name
        self.label = name
        self.routes = routes
        self._reason = reason
        self._route_reasons = route_reasons or {}

    def availability(self) -> str | None:
        return self._reason

    def route_availability(self, route: Route) -> str | None:
        return self._route_reasons.get(route)

    def convert(self, src: Path, dst: Path, route: Route) -> None:
        dst.write_bytes(b"x")


def _registry(structure_reason: str | None = None) -> Registry:
    return Registry(
        [
            FakeEngine("office", (Route(Format.DOCX, Format.PDF), Route(Format.DOCX, Format.DOC))),
            FakeEngine("layout", (Route(Format.PDF, Format.DOCX, Mode.LAYOUT, PdfKind.DIGITAL),)),
            FakeEngine(
                "structure",
                (
                    Route(Format.PDF, Format.DOCX, Mode.STRUCTURE, PdfKind.DIGITAL),
                    Route(Format.PDF, Format.DOCX, Mode.STRUCTURE, PdfKind.SCANNED),
                ),
                reason=structure_reason,
            ),
        ]
    )


def test_digital_pdf_offers_both_modes_for_docx_and_doc() -> None:
    options = {o.target: o.modes for o in _registry().options(DIGITAL)}
    assert options[Format.DOCX] == (Mode.LAYOUT, Mode.STRUCTURE)
    assert options[Format.DOC] == (Mode.LAYOUT, Mode.STRUCTURE)


def test_auto_mode_prefers_layout_for_digital_pdf() -> None:
    plan = _registry().resolve(DIGITAL, Format.DOCX, Mode.AUTO)
    assert [s.engine.name for s in plan] == ["layout"]


def test_requested_mode_is_honoured() -> None:
    plan = _registry().resolve(DIGITAL, Format.DOCX, Mode.STRUCTURE)
    assert plan[0].engine.name == "structure"


def test_pdf_to_doc_is_a_two_step_chain() -> None:
    plan = _registry().resolve(DIGITAL, Format.DOC, Mode.STRUCTURE)
    assert [(s.engine.name, s.route.target) for s in plan] == [("structure", Format.DOCX), ("office", Format.DOC)]


def test_scanned_pdf_falls_back_to_structure_when_layout_requested() -> None:
    plan = _registry().resolve(SCANNED, Format.DOCX, Mode.LAYOUT)
    assert plan[0].mode == Mode.STRUCTURE


def test_unavailable_engine_is_hidden_and_explained() -> None:
    registry = _registry(structure_reason="Docling absent")
    assert {o.target for o in registry.options(SCANNED)} == set()
    with pytest.raises(ConversionNotAvailable, match="Docling absent"):
        registry.resolve(SCANNED, Format.DOCX)


def test_route_level_requirement_hides_only_that_route() -> None:
    scanned_route = Route(Format.PDF, Format.DOCX, Mode.STRUCTURE, PdfKind.SCANNED)
    registry = Registry(
        [
            FakeEngine(
                "structure",
                (Route(Format.PDF, Format.DOCX, Mode.STRUCTURE, PdfKind.DIGITAL), scanned_route),
                route_reasons={scanned_route: "Tesseract absent"},
            )
        ]
    )
    assert [o.target for o in registry.options(DIGITAL)] == [Format.DOCX]
    assert registry.options(SCANNED) == []
    with pytest.raises(ConversionNotAvailable, match="Tesseract absent"):
        registry.resolve(SCANNED, Format.DOCX)


def test_unsupported_route() -> None:
    with pytest.raises(ConversionNotAvailable, match="non prise en charge"):
        _registry().resolve(Detection(format=Format.PNG), Format.DOCX)


def test_same_format_is_rejected() -> None:
    with pytest.raises(ConversionNotAvailable):
        _registry().resolve(Detection(format=Format.DOCX), Format.DOCX)


def test_matrix_lists_pdf_kinds_separately() -> None:
    rows = _registry().matrix()
    assert {"source": "pdf", "pdf_kind": "scanned", "target": "docx", "modes": ["structure"]} in rows
