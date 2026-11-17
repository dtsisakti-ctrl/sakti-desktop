"""Application errors, rendered as {"error": {"code", "message", "details"}}."""
from typing import Any


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def not_found(what: str = "resource") -> AppError:
    # Deliberately identical for "does not exist" and "belongs to another organization".
    return AppError(404, "NOT_FOUND", f"{what} not found")


def forbidden(message: str = "not allowed") -> AppError:
    return AppError(403, "FORBIDDEN", message)


def conflict(code: str, message: str, details: Any = None) -> AppError:
    return AppError(409, code, message, details)


def invalid(code: str, message: str, details: Any = None) -> AppError:
    return AppError(422, code, message, details)
