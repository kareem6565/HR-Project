import pytest

from app.services.errors import (
    ApplicationError,
    InvalidStateError,
    NotFoundError,
    ValidationError,
    VersionConflictError,
)

ERROR_SUBCLASSES = [NotFoundError, ValidationError, InvalidStateError, VersionConflictError]


def test_application_error_is_base_class() -> None:
    assert issubclass(ApplicationError, Exception)


@pytest.mark.parametrize("error_class", ERROR_SUBCLASSES)
def test_error_subclasses_inherit_from_application_error(error_class) -> None:
    assert issubclass(error_class, ApplicationError)


@pytest.mark.parametrize("error_class", ERROR_SUBCLASSES)
def test_error_subclasses_are_instantiable(error_class) -> None:
    error = error_class("oops")
    assert str(error) == "oops"
