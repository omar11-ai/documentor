"""Tests for offline fallback docs and generator fallback wiring."""

from pathlib import Path

from documentor.core.models import Entity, EntityType, Language, SourceLocation
from documentor.generation import fallback as fb
from documentor.generation.generator import DocumentationGenerator
from documentor.generation.model_client import ModelRouter
from documentor.core.models import KnowledgeGraph


def _entity(**overrides):
    base = {
        "id": "e1",
        "name": "add",
        "qualified_name": "api.add",
        "entity_type": EntityType.FUNCTION,
        "language": Language.PYTHON,
        "location": SourceLocation(file_path="src/api.py", start_line=1, end_line=5),
        "docstring": "Add two numbers.",
        "signature": "def add(a: int, b: int) -> int:",
    }
    base.update(overrides)
    return Entity(**base)


def test_render_entity_doc_contains_key_sections():
    doc = fb.render_entity_doc(_entity(), "def add(): ...", "None", "None")
    assert "# api.add" in doc
    assert "Signature" in doc
    assert "Docstring" in doc
    assert "Generated offline" in doc


def test_render_module_doc_lists_entities():
    mod = _entity(
        id="m1",
        name="api",
        qualified_name="api",
        entity_type=EntityType.MODULE,
    )
    doc = fb.render_module_doc(mod, [_entity()], "x = 1")
    assert "# Module: api" in doc
    assert "api.add" in doc
    assert "Generated offline" in doc


def test_generator_uses_fallback_when_no_model(tmp_path):
    graph = KnowledgeGraph()
    mod = _entity(
        id="m1",
        name="api",
        qualified_name="api",
        entity_type=EntityType.MODULE,
        location=SourceLocation(file_path=str(tmp_path / "api.py"), start_line=1, end_line=1),
    )
    ent = _entity(
        id="e1",
        location=SourceLocation(file_path=str(tmp_path / "api.py"), start_line=1, end_line=1),
    )
    (tmp_path / "api.py").write_text("def add(a, b):\n    return a + b\n")
    graph.add_entity(mod)
    graph.add_entity(ent)

    class DeadRouter(ModelRouter):
        def __init__(self):
            pass

        def generate(self, prompt, system_prompt="", **kwargs):
            from documentor.core.exceptions import ModelNotAvailableError

            raise ModelNotAvailableError("no model in test")

    gen = DocumentationGenerator(graph, model_router=DeadRouter())
    result = gen.generate_all(tmp_path / "docs")
    assert result.stats["errors"] == 0
    assert result.stats["fallback_docs"] == 2
    assert result.stats["llm_docs"] == 0
    assert (tmp_path / "docs" / "index.md").exists()
    assert (tmp_path / "docs" / "api.md").exists()
