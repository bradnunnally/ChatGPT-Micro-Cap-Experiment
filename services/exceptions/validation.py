from core.errors import ValidationError as _ValidationError


class ValidationError(_ValidationError):
    """Compatibility shim for legacy imports."""

    pass
