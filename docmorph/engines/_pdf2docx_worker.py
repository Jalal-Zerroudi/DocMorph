"""Child-process entry point: python -m docmorph.engines._pdf2docx_worker SRC DST"""

from __future__ import annotations

import sys

from pdf2docx import Converter


def main(src: str, dst: str) -> None:
    converter = Converter(src)
    try:
        converter.convert(dst, multi_processing=False)
    finally:
        converter.close()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
