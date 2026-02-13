"""File import exceptions.

Provides user-facing exception types for the import flow.
Server internals are never exposed to clients.
"""


class FileImportError(Exception):
    """Base exception for user-facing import errors."""

    def __init__(self, message: str, code: str = "import_error"):
        self.message = message
        self.code = code
        super().__init__(message)
