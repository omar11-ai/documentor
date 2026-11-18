"""Documentation generator using Nemotron models."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from documentor.core.models import (
    KnowledgeGraph,
    Entity,
    EntityType,
    Language,
)
from documentor.generation.model_client import ModelRouter, ModelResponse
from documentor.core.exceptions import ModelNotAvailableError
from documentor.generation import fallback as fallback_renderer
from documentor.generation.prompts import (
    SYSTEM_PROMPT,
    MODULE_DOC_PROMPT,
    CLASS_DOC_PROMPT,
    FUNCTION_DOC_PROMPT,
    ENTITY_DOC_PROMPT,
)
from documentor.core.config import get_config
from documentor.core.logging import get_logger
from documentor.core.exceptions import GenerationError

logger = get_logger(__name__)


@dataclass
class GenerationResult:
    """Result of documentation generation."""
    entity_docs: dict[str, str]  # entity_id -> markdown
    module_docs: dict[str, str]  # module_name -> markdown
    errors: list[str]
    stats: dict


class DocumentationGenerator:
    """Generates documentation from knowledge graph using Nemotron."""

    def __init__(self, graph: KnowledgeGraph, model_router: Optional[ModelRouter] = None):
        self.graph = graph
        self.model_router = model_router or ModelRouter()
        self.config = get_config()

    def generate_all(self, output_dir: Optional[Path] = None) -> GenerationResult:
        """Generate documentation for all entities in the graph."""
        logger.info(f"Generating documentation for {len(self.graph.entities)} entities")

        entity_docs = {}
        module_docs = {}
        errors = []
        llm_docs = 0
        fallback_docs = 0

        # Group entities by module
        modules: dict[str, list[Entity]] = {}
        for entity in self.graph.entities.values():
            if entity.entity_type == EntityType.MODULE:
                modules[entity.name] = []
            else:
                # Find module by file path
                module_name = Path(entity.location.file_path).stem
                modules.setdefault(module_name, []).append(entity)

        # Generate module docs first
        for module_name, entities in modules.items():
            module_entity = self._find_module_entity(module_name)
            if module_entity:
                try:
                    doc = self._generate_module_doc(module_entity, entities)
                    module_docs[module_name] = doc
                    if fallback_renderer.is_llm_doc(doc):
                        llm_docs += 1
                    else:
                        fallback_docs += 1
                except Exception as e:
                    errors.append(f"Module {module_name}: {e}")

        # Generate entity docs
        for entity in self.graph.entities.values():
            if entity.entity_type == EntityType.MODULE:
                continue
            try:
                doc = self._generate_entity_doc(entity)
                entity_docs[entity.id] = doc
                if fallback_renderer.is_llm_doc(doc):
                    llm_docs += 1
                else:
                    fallback_docs += 1
            except Exception as e:
                errors.append(f"Entity {entity.qualified_name}: {e}")

        # Write to output directory if specified
        if output_dir:
            self._write_output(output_dir, module_docs, entity_docs)

        stats = {
            "modules_documented": len(module_docs),
            "entities_documented": len(entity_docs),
            "errors": len(errors),
            "llm_docs": llm_docs,
            "fallback_docs": fallback_docs,
        }

        logger.info(f"Generation complete: {stats}")

        return GenerationResult(
            entity_docs=entity_docs,
            module_docs=module_docs,
            errors=errors,
            stats=stats,
        )

    def _find_module_entity(self, module_name: str) -> Optional[Entity]:
        """Find module entity by name."""
        for entity in self.graph.entities.values():
            if entity.entity_type == EntityType.MODULE and entity.name == module_name:
                return entity
        return None

    def _generate_module_doc(self, module: Entity, entities: list[Entity]) -> str:
        """Generate module-level documentation."""
        # Build context
        public_entities = [e for e in entities if e.role.value in ("public_api", "entry_point")]
        entities_summary = "\n".join(
            f"- {e.qualified_name} ({e.entity_type.value}): {e.docstring[:100] if e.docstring else 'No description'}"
            for e in public_entities[:20]
        )

        git_summary = ""
        if module.git_info:
            recent = "; ".join(c.message[:80] for c in module.git_info.recent_changes[:3])
            git_summary = (
                f"\n- Commits: {module.git_info.commit_count}"
                f"\n- Authors: {module.git_info.author_count}"
                f"\n- Recent changes: {recent}"
                f"\n- Bug fixes: {len(module.git_info.bug_fix_commits)}"
                f"\n- Features: {len(module.git_info.feature_commits)}"
            )

        prompt = MODULE_DOC_PROMPT.format(
            qualified_name=module.qualified_name,
            file_path=module.location.file_path,
            source_code=self._get_source_snippet(module),
            docstring=module.docstring or "None",
            commit_count=module.git_info.commit_count if module.git_info else 0,
            author_count=module.git_info.author_count if module.git_info else 0,
            recent_changes_summary=git_summary,
            bug_fix_count=len(module.git_info.bug_fix_commits) if module.git_info else 0,
            feature_count=len(module.git_info.feature_commits) if module.git_info else 0,
            entities_summary=entities_summary or "None",
        )

        return self._generate_with_fallback(
            prompt,
            SYSTEM_PROMPT,
            fallback_text=fallback_renderer.render_module_doc(
                module, entities, self._get_source_snippet(module)
            ),
        )

    def _generate_entity_doc(self, entity: Entity) -> str:
        """Generate documentation for a single entity."""
        # Choose prompt based on entity type
        if entity.entity_type == EntityType.CLASS:
            prompt_template = CLASS_DOC_PROMPT
        elif entity.entity_type in (EntityType.FUNCTION, EntityType.METHOD):
            prompt_template = FUNCTION_DOC_PROMPT
        else:
            prompt_template = ENTITY_DOC_PROMPT

        # Build context
        parent = self.graph.get_entity(entity.parent_id) if entity.parent_id else None
        children = self.graph.get_children(entity.id)
        callers = self.graph.get_callers(entity.id)
        callees = self.graph.get_callees(entity.id)

        git_summary = ""
        if entity.git_info:
            recent = "; ".join(c.message[:80] for c in entity.git_info.recent_changes[:3])
            git_summary = (
                f"\n- Commits: {entity.git_info.commit_count}"
                f"\n- Authors: {entity.git_info.author_count}"
                f"\n- Recent changes: {recent}"
                f"\n- Bug fixes: {len(entity.git_info.bug_fix_commits)}"
                f"\n- Features: {len(entity.git_info.feature_commits)}"
            )

        # Get source snippet
        source_snippet = self._get_source_snippet(entity)

        prompt = prompt_template.format(
            qualified_name=entity.qualified_name,
            entity_type=entity.entity_type.value,
            language=entity.language.value,
            file_path=entity.location.file_path,
            start_line=entity.location.start_line,
            end_line=entity.location.end_line,
            signature=entity.signature or "N/A",
            source_code=source_snippet,
            docstring=entity.docstring or "None",
            parent_name=parent.qualified_name if parent else "None",
            methods_summary=self._summarize_children(children),
            bases=self._get_bases(entity),
            callers_summary="; ".join(c.qualified_name for c in callers[:5]) or "None",
            callees_summary="; ".join(c.qualified_name for c in callees[:5]) or "None",
            commit_count=entity.git_info.commit_count if entity.git_info else 0,
            author_count=entity.git_info.author_count if entity.git_info else 0,
            recent_changes_summary=git_summary,
            bug_fix_count=len(entity.git_info.bug_fix_commits) if entity.git_info else 0,
            feature_count=len(entity.git_info.feature_commits) if entity.git_info else 0,
            calls_summary="; ".join(entity.calls[:10]) or "None",
            children_summary=self._summarize_children(children),
            imports_summary=", ".join(entity.imports[:10]) or "None",
        )

        callers_txt = "; ".join(c.qualified_name for c in callers[:5]) or "None"
        callees_txt = "; ".join(c.qualified_name for c in callees[:5]) or "None"
        return self._generate_with_fallback(
            prompt,
            SYSTEM_PROMPT,
            fallback_text=fallback_renderer.render_entity_doc(
                entity, source_snippet, callers_txt, callees_txt
            ),
        )

    def _generate_with_fallback(self, prompt: str, system_prompt: str, fallback_text: str) -> str:
        """Try LLM first, fall back to deterministic template offline."""
        try:
            response = self.model_router.generate(prompt, system_prompt)
            return response.content
        except ModelNotAvailableError:
            logger.info("No LLM available; using offline template fallback")
            return fallback_text

    def _get_source_snippet(self, entity: Entity, max_lines: int = 100) -> str:
        """Get source code snippet for entity."""
        try:
            file_path = Path(entity.location.file_path)
            if not file_path.exists():
                return "Source file not found"

            lines = file_path.read_text(encoding="utf-8").splitlines()
            start = max(0, entity.location.start_line - 1)
            end = min(len(lines), entity.location.end_line)
            snippet_lines = lines[start:end]

            if len(snippet_lines) > max_lines:
                snippet_lines = snippet_lines[:max_lines] + ["... (truncated)"]

            return "\n".join(snippet_lines)
        except Exception:
            return "Could not read source"

    def _summarize_children(self, children: list[Entity]) -> str:
        """Summarize child entities."""
        if not children:
            return "None"
        return "; ".join(f"{c.name} ({c.entity_type.value})" for c in children[:10])

    def _get_bases(self, entity: Entity) -> str:
        """Get base classes from source."""
        # This would need AST parsing - simplified for now
        return "Unknown"

    def _write_output(
        self,
        output_dir: Path,
        module_docs: dict[str, str],
        entity_docs: dict[str, str],
    ) -> None:
        """Write generated documentation to files."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Write module docs
        for module_name, doc in module_docs.items():
            (output_dir / f"{module_name}.md").write_text(doc, encoding="utf-8")

        # Write entity docs organized by module
        for entity_id, doc in entity_docs.items():
            entity = self.graph.entities[entity_id]
            module_name = Path(entity.location.file_path).stem
            module_dir = output_dir / module_name
            module_dir.mkdir(exist_ok=True)
            safe_name = entity.qualified_name.replace(".", "_").replace("<", "").replace(">", "")
            (module_dir / f"{safe_name}.md").write_text(doc, encoding="utf-8")

        # Write index
        index_content = self._generate_index(module_docs, entity_docs)
        (output_dir / "index.md").write_text(index_content, encoding="utf-8")

    def _generate_index(self, module_docs: dict[str, str], entity_docs: dict[str, str]) -> str:
        """Generate index page."""
        lines = ["# Documentation Index\n"]

        for module_name in sorted(module_docs.keys()):
            lines.append(f"## {module_name}")
            lines.append(f"- [Module Overview]({module_name}.md)")

            # Find entities for this module
            module_entities = [
                (eid, doc) for eid, doc in entity_docs.items()
                if Path(self.graph.entities[eid].location.file_path).stem == module_name
            ]

            for eid, doc in module_entities:
                entity = self.graph.entities[eid]
                safe_name = entity.qualified_name.replace(".", "_").replace("<", "").replace(">", "")
                lines.append(f"  - [{entity.qualified_name}]({module_name}/{safe_name}.md)")

            lines.append("")

        return "\n".join(lines)