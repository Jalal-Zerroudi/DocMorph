from __future__ import annotations


class DocMorphError(Exception):
    """Base error. `message` is shown to the user as-is (French)."""

    code = "error"
    http_status = 400

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def to_dict(self) -> dict[str, str | None]:
        return {"code": self.code, "message": self.message, "detail": self.detail}


class UnsupportedFormat(DocMorphError):
    code = "unsupported_format"
    http_status = 415


class ConversionNotAvailable(DocMorphError):
    code = "conversion_not_available"
    http_status = 422


class ConversionFailed(DocMorphError):
    code = "conversion_failed"
    http_status = 500


class FileTooLarge(DocMorphError):
    code = "file_too_large"
    http_status = 413


class Timeout(DocMorphError):
    code = "timeout"
    http_status = 504
