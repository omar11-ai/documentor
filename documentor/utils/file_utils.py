"""File system utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable
import pathspec


LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
}

TEST_PATTERNS = [
    "test_*.py",
    "*_test.py",
    "test.py",
    "test_*.js",
    "*_test.js",
    "test.js",
    "test_*.ts",
    "*_test.ts",
    "test.ts",
    "*_test.go",
    "*_test.rs",
    "*_spec.py",
    "*_spec.js",
    "*_spec.ts",
]


def find_files(
    root: Path,
    include_patterns: Iterable[str],
    exclude_patterns: Iterable[str],
) -> list[Path]:
    """Find files matching include patterns, excluding exclude patterns."""
    spec = pathspec.PathSpec.from_lines("gitwildmatch", exclude_patterns)
    files: list[Path] = []

    for pattern in include_patterns:
        for file_path in root.rglob(pattern):
            if file_path.is_file() and not spec.match_file(str(file_path.relative_to(root))):
                files.append(file_path)

    # Deduplicate while preserving order
    seen = set()
    unique_files = []
    for f in files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)

    return unique_files


def read_file(path: Path) -> str:
    """Read file content with encoding detection."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Try other encodings
        for encoding in ["latin-1", "cp1252"]:
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise


def write_file(path: Path, content: str) -> None:
    """Write file content, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def get_language_from_extension(path: Path) -> str | None:
    """Get language from file extension."""
    return LANGUAGE_EXTENSIONS.get(path.suffix.lower())


def is_test_file(path: Path) -> bool:
    """Check if file is a test file."""
    from fnmatch import fnmatch
    name = path.name
    return any(fnmatch(name, pattern) for pattern in TEST_PATTERNS)


def should_exclude(path: Path, exclude_patterns: Iterable[str]) -> bool:
    """Check if path should be excluded."""
    spec = pathspec.PathSpec.from_lines("gitwildmatch", exclude_patterns)
    try:
        rel_path = str(path.relative_to(Path.cwd()))
    except ValueError:
        rel_path = str(path)
    return spec.match_file(rel_path)