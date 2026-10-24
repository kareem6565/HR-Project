class ApplicationError(Exception):
    """Base class for deterministic application-service errors."""


class NotFoundError(ApplicationError):
    """Raised when a required domain record does not exist."""


class ValidationError(ApplicationError):
    """Raised when supplied data violates deterministic domain rules."""


class InvalidStateError(ApplicationError):
    """Raised when an operation is invalid for the record's current state."""


class VersionConflictError(ApplicationError):
    """Raised when a versioned insert conflicts with existing history."""


class ConflictError(ApplicationError):
    """Raised when a scheduling request overlaps an existing interview window."""


class StorageError(ApplicationError):
    """Base error for storage operations."""


class StoragePathTraversalError(StorageError, ValidationError):
    """Raised when a storage path or key attempts to escape the storage root."""


# ---------------------------------------------------------------------------
# Upload & Extraction Validation Error Codes (HERA Prompt 5)
# ---------------------------------------------------------------------------
UPLOAD_ERROR_UNSUPPORTED_TYPE = "UNSUPPORTED_TYPE"
UPLOAD_ERROR_TOO_LARGE = "TOO_LARGE"
UPLOAD_ERROR_CORRUPT = "CORRUPT"
UPLOAD_ERROR_ENCRYPTED = "ENCRYPTED"
UPLOAD_ERROR_NO_TEXT = "NO_TEXT"
UPLOAD_ERROR_PAGE_LIMIT_EXCEEDED = "PAGE_LIMIT_EXCEEDED"
UPLOAD_ERROR_INVALID_ARCHIVE = "INVALID_ARCHIVE"
UPLOAD_ERROR_BATCH_LIMIT_EXCEEDED = "BATCH_LIMIT_EXCEEDED"


class UploadValidationError(ValidationError):
    """Raised when an uploaded file or batch violates upload or extraction rules."""

    def __init__(self, message: str, *, code: str = UPLOAD_ERROR_CORRUPT) -> None:
        super().__init__(message)
        self.code = code
