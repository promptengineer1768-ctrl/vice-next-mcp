from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ViceError(Exception):
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    retriable: bool = False
    effect_may_have_occurred: bool = False

    def __str__(self) -> str:
        return self.message

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retriable": self.retriable,
            "effect_may_have_occurred": self.effect_may_have_occurred,
            "details": self.details,
        }


def invalid(message: str, **details: Any) -> ViceError:
    return ViceError("INVALID_REQUEST", message, details)


def verification(message: str, **details: Any) -> ViceError:
    return ViceError("VERIFICATION_FAILED", message, details)
