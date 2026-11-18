"""Base parser interface for DocuMentor."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from documentor.core.models import (
    Entity,
    EntityType,
    EntityRole,
    Stability,
    Language,
    SourceLocation,
    KnowledgeGraph,
    Relationship,
)
from documentor.core.exceptions import ParseError
from documentor.utils.hash_utils import generate_entity_id


class BaseParser(ABC):
    """Base class for language-specific parsers."""

    def __init__(self, language: Language):
        self.language = language
        self.graph = KnowledgeGraph()
        self._current_file: Optional[Path] = None
        self._file_content: str = ""

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """File extensions this parser supports."""
        pass

    @abstractmethod
    def parse_file(self, file_path: Path, content: str) -> list[Entity]:
        """Parse a single file and return extracted entities."""
        pass

    def parse_files(self, files: list[Path]) -> KnowledgeGraph:
        """Parse multiple files and build knowledge graph."""
        self.graph = KnowledgeGraph()
        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8")
                entities = self.parse_file(file_path, content)
                for entity in entities:
                    self.graph.add_entity(entity)
            except Exception as e:
                raise ParseError(f"Failed to parse {file_path}: {e}", str(file_path)) from e
        return self.graph

    def _create_entity(
        self,
        name: str,
        qualified_name: str,
        entity_type: EntityType,
        location: SourceLocation,
        signature: Optional[str] = None,
        docstring: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> Entity:
        """Create an entity with generated ID."""
        entity_id = generate_entity_id(
            qualified_name=qualified_name,
            entity_type=entity_type.value,
            file_path=location.file_path,
            language=self.language.value,
        )
        return Entity(
            id=entity_id,
            name=name,
            qualified_name=qualified_name,
            entity_type=entity_type,
            language=self.language,
            location=location,
            signature=signature,
            docstring=docstring,
            parent_id=parent_id,
        )

    def _add_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        metadata: dict | None = None,
    ) -> None:
        """Add a relationship to the graph."""
        from documentor.core.models import Relationship
        rel = Relationship(
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
            metadata=metadata or {},
        )
        self.graph.add_relationship(rel)

    def _make_location(
        self,
        file_path: Path,
        start_line: int,
        end_line: int,
        start_col: int = 0,
        end_col: int = 0,
    ) -> SourceLocation:
        """Create a SourceLocation."""
        return SourceLocation(
            file_path=str(file_path),
            start_line=start_line,
            end_line=end_line,
            start_col=start_col,
            end_col=end_col,
        )