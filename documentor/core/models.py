"""Core data models for DocuMentor knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import json


class EntityType(str, Enum):
    """Types of code entities."""

    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    PROPERTY = "property"
    VARIABLE = "variable"
    CONSTANT = "constant"
    TYPE_ALIAS = "type_alias"
    INTERFACE = "interface"
    ENUM = "enum"
    STRUCT = "struct"
    TRAIT = "trait"
    IMPL = "impl"


class EntityRole(str, Enum):
    """Semantic role of an entity in the codebase."""

    PUBLIC_API = "public_api"          # Exported, intended for external use
    INTERNAL = "internal"              # Internal implementation detail
    CONFIG = "config"                  # Configuration/constants
    TEST = "test"                      # Test code
    UTILITY = "utility"                # Helper/utility function
    ENTRY_POINT = "entry_point"        # Main, CLI, handler
    DATA_MODEL = "data_model"          # DTO, entity, schema
    PROTOCOL = "protocol"              # Interface, ABC, trait
    MIXIN = "mixin"                    # Mixin class
    DECORATOR = "decorator"            # Decorator function
    CONTEXT_MANAGER = "context_manager"  # Context manager
    UNKNOWN = "unknown"


class Stability(str, Enum):
    """Stability classification."""

    STABLE = "stable"
    EXPERIMENTAL = "experimental"
    DEPRECATED = "deprecated"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


class Language(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"


@dataclass
class SourceLocation:
    """Source code location."""

    file_path: str
    start_line: int
    end_line: int
    start_col: int = 0
    end_col: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "start_col": self.start_col,
            "end_col": self.end_col,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceLocation:
        return cls(**data)


@dataclass
class Entity:
    """A code entity in the knowledge graph."""

    id: str
    name: str
    qualified_name: str
    entity_type: EntityType
    language: Language
    location: SourceLocation
    role: EntityRole = EntityRole.UNKNOWN
    stability: Stability = Stability.UNKNOWN
    docstring: Optional[str] = None
    signature: Optional[str] = None
    parent_id: Optional[str] = None
    children_ids: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)  # IDs of called entities
    called_by: list[str] = field(default_factory=list)  # IDs of callers
    imports: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    git_info: Optional[GitInfo] = None
    embedding: Optional[list[float]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "qualified_name": self.qualified_name,
            "entity_type": self.entity_type.value,
            "language": self.language.value,
            "location": self.location.to_dict(),
            "role": self.role.value,
            "stability": self.stability.value,
            "docstring": self.docstring,
            "signature": self.signature,
            "parent_id": self.parent_id,
            "children_ids": self.children_ids,
            "calls": self.calls,
            "called_by": self.called_by,
            "imports": self.imports,
            "metadata": self.metadata,
            "git_info": self.git_info.to_dict() if self.git_info else None,
            "embedding": self.embedding,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Entity:
        data = data.copy()
        data["entity_type"] = EntityType(data["entity_type"])
        data["language"] = Language(data["language"])
        data["role"] = EntityRole(data["role"])
        data["stability"] = Stability(data["stability"])
        data["location"] = SourceLocation.from_dict(data["location"])
        if data.get("git_info"):
            data["git_info"] = GitInfo.from_dict(data["git_info"])
        if data.get("created_at"):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


@dataclass
class GitInfo:
    """Git history information for an entity."""

    file_path: str
    first_commit: str
    last_commit: str
    commit_count: int
    author_count: int
    last_modified: datetime
    recent_changes: list[CommitInfo] = field(default_factory=list)
    co_change_files: list[str] = field(default_factory=list)
    bug_fix_commits: list[str] = field(default_factory=list)
    feature_commits: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "first_commit": self.first_commit,
            "last_commit": self.last_commit,
            "commit_count": self.commit_count,
            "author_count": self.author_count,
            "last_modified": self.last_modified.isoformat(),
            "recent_changes": [c.to_dict() for c in self.recent_changes],
            "co_change_files": self.co_change_files,
            "bug_fix_commits": self.bug_fix_commits,
            "feature_commits": self.feature_commits,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GitInfo:
        data = data.copy()
        data["last_modified"] = datetime.fromisoformat(data["last_modified"])
        data["recent_changes"] = [CommitInfo.from_dict(c) for c in data.get("recent_changes", [])]
        return cls(**data)


@dataclass
class CommitInfo:
    """Information about a single commit."""

    hash: str
    message: str
    author: str
    date: datetime
    files_changed: list[str] = field(default_factory=list)
    is_bug_fix: bool = False
    is_feature: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "hash": self.hash,
            "message": self.message,
            "author": self.author,
            "date": self.date.isoformat(),
            "files_changed": self.files_changed,
            "is_bug_fix": self.is_bug_fix,
            "is_feature": self.is_feature,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CommitInfo:
        data = data.copy()
        data["date"] = datetime.fromisoformat(data["date"])
        return cls(**data)


@dataclass
class Relationship:
    """Relationship between two entities."""

    source_id: str
    target_id: str
    relationship_type: str  # calls, inherits, implements, uses, imports, contains
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship_type": self.relationship_type,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Relationship:
        return cls(**data)


@dataclass
class KnowledgeGraph:
    """The complete knowledge graph for a codebase."""

    entities: dict[str, Entity] = field(default_factory=dict)
    relationships: list[Relationship] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def add_entity(self, entity: Entity) -> None:
        self.entities[entity.id] = entity
        self.updated_at = datetime.utcnow()

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self.entities.get(entity_id)

    def add_relationship(self, rel: Relationship) -> None:
        self.relationships.append(rel)
        self.updated_at = datetime.utcnow()

    def get_callers(self, entity_id: str) -> list[Entity]:
        return [self.entities[eid] for eid in self.entities[entity_id].called_by if eid in self.entities]

    def get_callees(self, entity_id: str) -> list[Entity]:
        return [self.entities[eid] for eid in self.entities[entity_id].calls if eid in self.entities]

    def get_children(self, entity_id: str) -> list[Entity]:
        return [self.entities[eid] for eid in self.entities[entity_id].children_ids if eid in self.entities]

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": {k: v.to_dict() for k, v in self.entities.items()},
            "relationships": [r.to_dict() for r in self.relationships],
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeGraph:
        kg = cls()
        kg.entities = {k: Entity.from_dict(v) for k, v in data.get("entities", {}).items()}
        kg.relationships = [Relationship.from_dict(r) for r in data.get("relationships", [])]
        kg.metadata = data.get("metadata", {})
        if data.get("created_at"):
            kg.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            kg.updated_at = datetime.fromisoformat(data["updated_at"])
        return kg