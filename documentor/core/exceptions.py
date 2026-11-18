"""Custom exceptions for DocuMentor."""

from __future__ import annotations


class DocumentorError(Exception):
    """Base exception for DocuMentor."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(DocumentorError):
    """Configuration-related errors."""

    pass


class AnalysisError(DocumentorError):
    """Code analysis errors."""

    pass


class ParseError(AnalysisError):
    """Parsing errors for specific files."""

    def __init__(self, message: str, file_path: str, line: int | None = None):
        super().__init__(message, {"file_path": file_path, "line": line})
        self.file_path = file_path
        self.line = line


class GenerationError(DocumentorError):
    """Documentation generation errors."""

    pass


class ModelError(DocumentorError):
    """LLM model-related errors."""

    pass


class ModelNotAvailableError(ModelError):
    """Requested model is not available."""

    pass


class NebiusError(DocumentorError):
    """Nebius API errors."""

    pass


class CacheError(DocumentorError):
    """Cache/storage errors."""

    pass


class GitError(DocumentorError):
    """Git operation errors."""

    pass