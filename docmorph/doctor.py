"""Diagnostic : python -m docmorph.doctor"""

from __future__ import annotations

from docmorph.config import settings
from docmorph.core.registry import Registry
from docmorph.engines import default_engines
from docmorph.engines.pdf_structure import PdfStructureEngine, preferred_device


def main() -> None:
    registry = Registry(default_engines())
    print("Moteurs :")
    for engine in registry.engines:
        reason = registry.unavailable_reason(engine)
        status = "OK" if reason is None else f"INDISPONIBLE - {reason}"
        print(f"  {engine.label:<34} {status}")
        if isinstance(engine, PdfStructureEngine) and reason is None:
            print(f"  {'':<34} périphérique : {preferred_device()}")

    print(f"\nDossier temporaire : {settings.data_dir}")
    print(f"Modèles Docling    : {settings.docling_artifacts or 'cache Hugging Face (téléchargement à la demande)'}")
    print(f"Langues OCR        : {'+'.join(settings.ocr_langs)}")

    print("\nConversions disponibles :")
    for row in registry.matrix():
        kind = f" ({'scanné' if row['pdf_kind'] == 'scanned' else 'numérique'})" if row["pdf_kind"] else ""
        modes = f"  [{', '.join(row['modes'])}]" if len(row["modes"]) > 1 else ""
        print(f"  {row['source'].upper()}{kind} -> {row['target'].upper()}{modes}")


if __name__ == "__main__":
    main()
