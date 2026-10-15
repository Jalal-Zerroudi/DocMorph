from __future__ import annotations


def is_mostly_arabic(text: str) -> bool:
    arabic = sum(1 for c in text if "\u0600" <= c <= "\u06ff" or "\u0750" <= c <= "\u077f")
    latin = sum(1 for c in text if c.isascii() and c.isalpha())
    return arabic > latin
