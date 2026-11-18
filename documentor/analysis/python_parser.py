"""Python parser using libcst."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import libcst as cst
from libcst.metadata import PositionProvider, ParentNodeProvider

from documentor.analysis.parser_base import BaseParser
from documentor.core.models import (
    Entity,
    EntityType,
    EntityRole,
    Stability,
    Language,
    SourceLocation,
)
from documentor.utils.hash_utils import generate_entity_id


class PythonParser(BaseParser):
    """Python code parser using libcst."""

    @property
    def supported_extensions(self) -> list[str]:
        return [".py"]

    def parse_file(self, file_path: Path, content: str) -> list[Entity]:
        """Parse a Python file and extract entities."""
        self._current_file = file_path
        self._file_content = content

        try:
            module = cst.parse_module(content)
        except cst.ParserSyntaxError as e:
            # Try to recover by parsing with error tolerance
            raise

        # Collect metadata
        wrapper = cst.MetadataWrapper(module)
        positions = wrapper.resolve(PositionProvider)
        parents = wrapper.resolve(ParentNodeProvider)

        visitor = _PythonVisitor(
            file_path=file_path,
            content=content,
            positions=positions,
            parents=parents,
            language=self.language,
        )
        module.visit(visitor)

        return visitor.entities


class _PythonVisitor(cst.CSTVisitor):
    """Visitor to extract Python entities."""

    METADATA_DEPENDENCIES = (PositionProvider, ParentNodeProvider)

    def __init__(
        self,
        file_path: Path,
        content: str,
        positions: dict,
        parents: dict,
        language: Language,
    ):
        super().__init__()
        self.file_path = file_path
        self.content = content
        self.positions = positions
        self.parents = parents
        self.language = language
        self.entities: list[Entity] = []
        self._current_class: Optional[Entity] = None
        self._current_function: Optional[Entity] = None
        self._module_entity: Optional[Entity] = None
        self._imports: list[str] = []
        self._calls: dict[str, list[str]] = {}  # entity_id -> list of called qualified names

    def _get_location(self, node: cst.CSTNode) -> SourceLocation:
        """Get source location for a node."""
        pos = self.positions.get(node)
        if pos:
            start = pos.start
            end = pos.end
            return SourceLocation(
                file_path=str(self.file_path),
                start_line=start.line,
                end_line=end.line,
                start_col=start.column,
                end_col=end.column,
            )
        return SourceLocation(
            file_path=str(self.file_path),
            start_line=1,
            end_line=1,
        )

    def _get_signature(self, node: cst.CSTNode) -> str:
        """Get source code signature for a node."""
        return self.content[node.metadata(PositionProvider).start.line - 1:
                           node.metadata(PositionProvider).end.line].strip() if node in self.positions else ""

    def _get_docstring(self, node: cst.CSTNode) -> Optional[str]:
        """Extract docstring from a node."""
        if isinstance(node, (cst.FunctionDef, cst.ClassDef, cst.Module)):
            body = node.body
            if isinstance(body, cst.IndentedBlock):
                first_stmt = body.body[0] if body.body else None
                if isinstance(first_stmt, cst.SimpleStatementLine):
                    expr = first_stmt.body[0] if first_stmt.body else None
                    if isinstance(expr, cst.Expr) and isinstance(expr.value, cst.SimpleString):
                        return expr.value.value.strip('"\'')
        return None

    def _get_qualified_name(self, name: str) -> str:
        """Build qualified name with current context."""
        parts = []
        if self._current_class:
            parts.append(self._current_class.name)
        parts.append(name)
        return ".".join(parts)

    def visit_Module(self, node: cst.Module) -> None:
        """Visit module node."""
        location = self._get_location(node)
        docstring = self._get_docstring(node)

        entity = Entity(
            id=generate_entity_id(
                qualified_name=self.file_path.stem,
                entity_type=EntityType.MODULE.value,
                file_path=str(self.file_path),
                language=self.language.value,
            ),
            name=self.file_path.stem,
            qualified_name=self.file_path.stem,
            entity_type=EntityType.MODULE,
            language=self.language,
            location=location,
            docstring=docstring,
        )
        self._module_entity = entity
        self.entities.append(entity)

    def leave_Module(self, node: cst.Module) -> None:
        self._module_entity = None

    def visit_Import(self, node: cst.Import) -> None:
        """Collect imports."""
        for alias in node.names:
            self._imports.append(alias.name.value)

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        """Collect from imports."""
        module = node.module
        if module:
            base = ".".join(n.value for n in module.name)
            for alias in node.names:
                self._imports.append(f"{base}.{alias.name.value}")

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        """Visit class definition."""
        location = self._get_location(node)
        signature = self._get_signature(node)
        docstring = self._get_docstring(node)
        qualified_name = self._get_qualified_name(node.name.value)

        entity = Entity(
            id=generate_entity_id(
                qualified_name=qualified_name,
                entity_type=EntityType.CLASS.value,
                file_path=str(self.file_path),
                language=self.language.value,
            ),
            name=node.name.value,
            qualified_name=qualified_name,
            entity_type=EntityType.CLASS,
            language=self.language,
            location=location,
            signature=signature,
            docstring=docstring,
            parent_id=self._current_class.id if self._current_class else self._module_entity.id if self._module_entity else None,
            imports=self._imports.copy(),
        )

        # Determine role
        entity.role = self._classify_class_role(entity, node)

        if self._current_class:
            self._current_class.children_ids.append(entity.id)
        elif self._module_entity:
            self._module_entity.children_ids.append(entity.id)

        self.entities.append(entity)
        self._current_class = entity
        self._calls[entity.id] = []

    def leave_ClassDef(self, node: cst.ClassDef) -> None:
        self._current_class = None

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        """Visit function definition."""
        location = self._get_location(node)
        signature = self._get_signature(node)
        docstring = self._get_docstring(node)
        qualified_name = self._get_qualified_name(node.name.value)

        # Determine if method or function
        is_method = self._current_class is not None
        entity_type = EntityType.METHOD if is_method else EntityType.FUNCTION

        entity = Entity(
            id=generate_entity_id(
                qualified_name=qualified_name,
                entity_type=entity_type.value,
                file_path=str(self.file_path),
                language=self.language.value,
            ),
            name=node.name.value,
            qualified_name=qualified_name,
            entity_type=entity_type,
            language=self.language,
            location=location,
            signature=signature,
            docstring=docstring,
            parent_id=self._current_class.id if self._current_class else self._module_entity.id if self._module_entity else None,
            imports=self._imports.copy(),
        )

        # Determine role
        entity.role = self._classify_function_role(entity, node)

        if self._current_class:
            self._current_class.children_ids.append(entity.id)
        elif self._module_entity:
            self._module_entity.children_ids.append(entity.id)

        self.entities.append(entity)
        self._current_function = entity
        self._calls[entity.id] = []

    def leave_FunctionDef(self, node: cst.FunctionDef) -> None:
        self._current_function = None

    def visit_Call(self, node: cst.Call) -> None:
        """Track function calls."""
        if self._current_function:
            func = node.func
            if isinstance(func, cst.Name):
                self._calls[self._current_function.id].append(func.value)
            elif isinstance(func, cst.Attribute):
                # Try to get full attribute chain
                parts = []
                current = func
                while isinstance(current, cst.Attribute):
                    parts.append(current.attr.value)
                    current = current.value
                if isinstance(current, cst.Name):
                    parts.append(current.value)
                parts.reverse()
                self._calls[self._current_function.id].append(".".join(parts))

    def _classify_class_role(self, entity: Entity, node: cst.ClassDef) -> EntityRole:
        """Classify the role of a class."""
        name = entity.name.lower()
        bases = [base.value.value if isinstance(base.value, cst.Name) else "" for base in node.bases]

        # Check for common patterns
        if any("ABC" in b or "Protocol" in b for b in bases):
            return EntityRole.PROTOCOL
        if "mixin" in name:
            return EntityRole.MIXIN
        if name.endswith("model") or name.endswith("schema") or name.endswith("dto"):
            return EntityRole.DATA_MODEL
        if name.startswith("Test") or name.endswith("Test"):
            return EntityRole.TEST
        if name.endswith("Exception") or name.endswith("Error"):
            return EntityRole.INTERNAL
        if entity.parent_id is None or (self._module_entity and entity.parent_id == self._module_entity.id):
            # Top-level class - likely public API
            return EntityRole.PUBLIC_API
        return EntityRole.INTERNAL

    def _classify_function_role(self, entity: Entity, node: cst.FunctionDef) -> EntityRole:
        """Classify the role of a function."""
        name = entity.name.lower()

        if name.startswith("test_"):
            return EntityRole.TEST
        if name.startswith("_"):
            return EntityRole.INTERNAL
        if name in ("__init__", "__new__", "__enter__", "__exit__"):
            return EntityRole.INTERNAL
        if entity.parent_id and self._current_class:
            # Method - check decorators
            for deco in node.decorators:
                if isinstance(deco.decorator, cst.Name):
                    if deco.decorator.value in ("property", "cached_property"):
                        return EntityRole.PROPERTY
                    if deco.decorator.value in ("classmethod", "staticmethod"):
                        return EntityRole.INTERNAL
        # Top-level function
        if entity.parent_id is None or (self._module_entity and entity.parent_id == self._module_entity.id):
            if name == "main":
                return EntityRole.ENTRY_POINT
            return EntityRole.PUBLIC_API
        return EntityRole.INTERNAL