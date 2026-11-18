"""Tests for core models."""

import pytest
from pathlib import Path
from datetime import datetime

from documentor.core.models import (
    Entity,
    EntityType,
    EntityRole,
    Stability,
    Language,
    SourceLocation,
    GitInfo,
    CommitInfo,
    Relationship,
    KnowledgeGraph,
)


class TestSourceLocation:
    def test_to_dict(self):
        loc = SourceLocation(
            file_path="test.py",
            start_line=10,
            end_line=20,
            start_col=4,
            end_col=8,
        )
        data = loc.to_dict()
        assert data["file_path"] == "test.py"
        assert data["start_line"] == 10
        assert data["end_line"] == 20

    def test_from_dict(self):
        data = {
            "file_path": "test.py",
            "start_line": 10,
            "end_line": 20,
            "start_col": 4,
            "end_col": 8,
        }
        loc = SourceLocation.from_dict(data)
        assert loc.file_path == "test.py"
        assert loc.start_line == 10


class TestEntity:
    def test_create_entity(self):
        entity = Entity(
            id="abc123",
            name="MyClass",
            qualified_name="module.MyClass",
            entity_type=EntityType.CLASS,
            language=Language.PYTHON,
            location=SourceLocation(file_path="test.py", start_line=1, end_line=10),
        )
        assert entity.id == "abc123"
        assert entity.name == "MyClass"
        assert entity.entity_type == EntityType.CLASS

    def test_to_dict(self):
        entity = Entity(
            id="abc123",
            name="MyClass",
            qualified_name="module.MyClass",
            entity_type=EntityType.CLASS,
            language=Language.PYTHON,
            location=SourceLocation(file_path="test.py", start_line=1, end_line=10),
        )
        data = entity.to_dict()
        assert data["id"] == "abc123"
        assert data["entity_type"] == "class"
        assert data["language"] == "python"

    def test_from_dict(self):
        data = {
            "id": "abc123",
            "name": "MyClass",
            "qualified_name": "module.MyClass",
            "entity_type": "class",
            "language": "python",
            "location": {
                "file_path": "test.py",
                "start_line": 1,
                "end_line": 10,
                "start_col": 0,
                "end_col": 0,
            },
            "role": "public_api",
            "stability": "stable",
            "docstring": None,
            "signature": None,
            "parent_id": None,
            "children_ids": [],
            "calls": [],
            "called_by": [],
            "imports": [],
            "metadata": {},
            "git_info": None,
            "embedding": None,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        entity = Entity.from_dict(data)
        assert entity.id == "abc123"
        assert entity.entity_type == EntityType.CLASS
        assert entity.role == EntityRole.PUBLIC_API


class TestKnowledgeGraph:
    def test_add_entity(self):
        graph = KnowledgeGraph()
        entity = Entity(
            id="abc123",
            name="MyClass",
            qualified_name="module.MyClass",
            entity_type=EntityType.CLASS,
            language=Language.PYTHON,
            location=SourceLocation(file_path="test.py", start_line=1, end_line=10),
        )
        graph.add_entity(entity)
        assert "abc123" in graph.entities
        assert graph.get_entity("abc123") == entity

    def test_get_entity_not_found(self):
        graph = KnowledgeGraph()
        assert graph.get_entity("nonexistent") is None

    def test_add_relationship(self):
        graph = KnowledgeGraph()
        rel = Relationship(
            source_id="a",
            target_id="b",
            relationship_type="calls",
        )
        graph.add_relationship(rel)
        assert len(graph.relationships) == 1
        assert graph.relationships[0].source_id == "a"


class TestGitInfo:
    def test_git_info_serialization(self):
        git_info = GitInfo(
            file_path="test.py",
            first_commit="abc123",
            last_commit="def456",
            commit_count=10,
            author_count=2,
            last_modified=datetime(2024, 1, 1),
        )
        data = git_info.to_dict()
        assert data["commit_count"] == 10
        assert data["author_count"] == 2

        restored = GitInfo.from_dict(data)
        assert restored.commit_count == 10
        assert restored.author_count == 2


class TestCommitInfo:
    def test_commit_info_serialization(self):
        commit = CommitInfo(
            hash="abc123",
            message="Fix bug",
            author="John Doe",
            date=datetime(2024, 1, 1),
            is_bug_fix=True,
        )
        data = commit.to_dict()
        assert data["is_bug_fix"] is True
        assert data["message"] == "Fix bug"

        restored = CommitInfo.from_dict(data)
        assert restored.is_bug_fix is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])