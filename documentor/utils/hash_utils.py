"""Hashing utilities for DocuMentor."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
import xxhash


def hash_content(content: str) -> str:
    """Generate deterministic hash for content."""
    return xxhash.xxh64(content.encode("utf-8")).hexdigest()


def hash_file(path: Path) -> str:
    """Generate hash for file content."""
    with open(path, "rb") as f:
        return xxhash.xxh64(f.read()).hexdigest()


def generate_entity_id(
    qualified_name: str,
    entity_type: str,
    file_path: str,
    language: str,
) -> str:
    """Generate unique entity ID from components."""
    content = f"{language}:{file_path}:{entity_type}:{qualified_name}"
    return xxhash.xxh64(content.encode("utf-8")).hexdigest()[:16]


def hash_dict(data: dict[str, Any]) -> str:
    """Generate deterministic hash for dictionary."""
    import json
    content = json.dumps(data, sort_keys=True, default=str)
    return hash_content(content)