"""Tree-sitter parser for JavaScript, TypeScript, Go, Rust."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import tree_sitter
from tree_sitter import Parser

# Aliased: documentor.core.models also defines a `Language` enum, and that
# import shadows tree_sitter's Language class further down the import block.
from tree_sitter import Language as TS_Language

try:  # tree-sitter >= 0.25 moved query compilation onto the Query class
    from tree_sitter import Query as _TreeSitterQuery
except ImportError:  # pragma: no cover - older tree-sitter
    _TreeSitterQuery = None

try:  # tree-sitter >= 0.25 runs queries through a QueryCursor
    from tree_sitter import QueryCursor as _QueryCursor
except ImportError:  # pragma: no cover - older tree-sitter
    _QueryCursor = None

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
from documentor.core.logging import get_logger

logger = get_logger(__name__)


# Language configurations
TREE_SITTER_LANGUAGES = {
    Language.JAVASCRIPT: ("tree_sitter_javascript", "language"),
    Language.TYPESCRIPT: ("tree_sitter_typescript", "language_typescript"),
    Language.GO: ("tree_sitter_go", "language"),
    Language.RUST: ("tree_sitter_rust", "language"),
}

# Query patterns for each language
QUERIES = {
    Language.JAVASCRIPT: {
        "function": "(function_declaration name: (identifier) @name)",
        "method": "(method_definition name: (property_identifier) @name)",
        "class": "(class_declaration name: (identifier) @name)",
        "variable": "(variable_declarator name: (identifier) @name)",
        # `const f = () => {}` is how most JavaScript functions are written,
        # so it has to be captured explicitly or the API reference is empty.
        "arrow_function": "(variable_declarator name: (identifier) @name "
                          "value: (arrow_function))",
        "import": "(import_statement) @import",
    },
    Language.TYPESCRIPT: {
        "function": "(function_declaration name: (identifier) @name)",
        "method": "(method_definition name: (property_identifier) @name)",
        # In tree-sitter-typescript a class name is a type_identifier, not an
        # identifier - using identifier here makes the whole query invalid.
        "class": "(class_declaration name: (type_identifier) @name)",
        "interface": "(interface_declaration name: (type_identifier) @name)",
        "type": "(type_alias_declaration name: (type_identifier) @name)",
        "variable": "(variable_declarator name: (identifier) @name)",
        "arrow_function": "(variable_declarator name: (identifier) @name "
                          "value: (arrow_function))",
        "import": "(import_statement) @import",
    },
    Language.GO: {
        "function": "(function_declaration name: (identifier) @name)",
        "method": "(method_declaration name: (field_identifier) @name)",
        "struct": "(type_spec name: (type_identifier) @name)",
        "interface": "(interface_type) @interface",
        "import": "(import_spec) @import",
    },
    Language.RUST: {
        "function": "(function_item name: (identifier) @name)",
        # An impl block has no `name` field - the type it implements is under
        # `type`, and the trait it implements under `trait`.
        "method": "(impl_item type: (type_identifier) @name)",
        "struct": "(struct_item name: (type_identifier) @name)",
        "enum": "(enum_item name: (type_identifier) @name)",
        "trait": "(trait_item name: (type_identifier) @name)",
        "impl": "(impl_item) @impl",
        "import": "(use_declaration) @import",
    },
}


class TreeSitterParser(BaseParser):
    """Parser using tree-sitter for multiple languages."""

    def __init__(self, language: Language):
        super().__init__(language)
        self._parser: Optional[Parser] = None
        self._language: Optional[Language] = None
        self._queries: dict[str, tree_sitter.Query] = {}
        self._init_parser()

    def _init_parser(self) -> None:
        """Initialize tree-sitter parser for the language."""
        if self.language not in TREE_SITTER_LANGUAGES:
            return

        module_name, attr_name = TREE_SITTER_LANGUAGES[self.language]
        try:
            module = __import__(module_name, fromlist=[attr_name])
            raw_language = getattr(module, attr_name)
            # Newer tree-sitter language packages expose a factory function
            # returning a PyCapsule; older ones expose the capsule directly.
            if callable(raw_language):
                raw_language = raw_language()
            ts_language = (
                raw_language
                if isinstance(raw_language, TS_Language)
                else TS_Language(raw_language)
            )
            self._language = ts_language
            self._parser = Parser()

            # tree-sitter 0.25+ removed Parser.set_language() in favour of a
            # plain `language` property. Support both so the package works on
            # whichever tree-sitter is installed.
            if hasattr(self._parser, "set_language"):
                self._parser.set_language(ts_language)
            else:
                self._parser.language = ts_language

            # Compile queries. A single bad pattern must not take the whole
            # language down, so failures are skipped rather than fatal.
            for name, pattern in QUERIES.get(self.language, {}).items():
                try:
                    self._queries[name] = self._compile_query(ts_language, pattern)
                except Exception as exc:
                    logger.warning(
                        f"Skipping invalid {self.language.value} query "
                        f"'{name}': {exc}"
                    )
        except ImportError:
            pass  # Language not available

    @staticmethod
    def _compile_query(ts_language, pattern: str):
        """Compile a query, supporting both tree-sitter API generations."""
        if _TreeSitterQuery is not None:
            return _TreeSitterQuery(ts_language, pattern)
        return ts_language.query(pattern)

    @property
    def supported_extensions(self) -> list[str]:
        ext_map = {
            Language.JAVASCRIPT: [".js", ".jsx"],
            Language.TYPESCRIPT: [".ts", ".tsx"],
            Language.GO: [".go"],
            Language.RUST: [".rs"],
        }
        return ext_map.get(self.language, [])

    def parse_file(self, file_path: Path, content: str) -> list[Entity]:
        """Parse a file using tree-sitter."""
        if not self._parser or not self._language:
            return []

        self._current_file = file_path
        self._file_content = content

        try:
            tree = self._parser.parse(content.encode("utf-8"))
        except Exception:
            return []

        entities = self._extract_entities(tree.root_node, content)
        return entities

    def _extract_entities(self, root: tree_sitter.Node, content: str) -> list[Entity]:
        """Extract entities from tree-sitter AST."""
        entities: list[Entity] = []
        imports: list[str] = []

        # Get module entity
        module_name = self._current_file.stem
        module_entity = Entity(
            id=generate_entity_id(
                qualified_name=module_name,
                entity_type=EntityType.MODULE.value,
                file_path=str(self._current_file),
                language=self.language.value,
            ),
            name=module_name,
            qualified_name=module_name,
            entity_type=EntityType.MODULE,
            language=self.language,
            location=SourceLocation(
                file_path=str(self._current_file),
                start_line=1,
                end_line=content.count("\n") + 1,
            ),
        )
        entities.append(module_entity)

        # Extract imports
        if "import" in self._queries:
            captures = self._capture(self._queries["import"], root)
            for node, name in captures:
                imports.append(content[node.start_byte:node.end_byte])

        # Extract functions
        if "function" in self._queries:
            captures = self._capture(self._queries["function"], root)
            for node, name in captures:
                if name == "name":
                    func_node = node.parent
                    while func_node and func_node.type not in ("function_declaration", "function_item", "method_declaration", "method_item"):
                        func_node = func_node.parent
                    if func_node:
                        entity = self._create_entity_from_node(
                            func_node, content, EntityType.FUNCTION, module_entity.id
                        )
                        if entity:
                            entities.append(entity)

        # Extract arrow functions assigned to a variable
        if "arrow_function" in self._queries:
            captures = self._capture(self._queries["arrow_function"], root)
            for node, capture_name in captures:
                if capture_name != "name":
                    continue
                declarator = node.parent
                if declarator is None or declarator.type != "variable_declarator":
                    continue
                value = next((c for c in declarator.children
                              if c.type == "arrow_function"), None)
                if value is None:
                    continue
                entity = self._create_entity_from_node(
                    value, content, EntityType.FUNCTION, module_entity.id,
                    name_node=node,
                )
                if entity:
                    entities.append(entity)

        # Extract classes/structs
        for entity_type, query_name in [
            (EntityType.CLASS, "class"),
            (EntityType.INTERFACE, "interface"),
            (EntityType.STRUCT, "struct"),
            (EntityType.TRAIT, "trait"),
        ]:
            if query_name in self._queries:
                captures = self._capture(self._queries[query_name], root)
                for node, name in captures:
                    if name == "name":
                        type_node = node.parent
                        while type_node and type_node.type not in (query_name + "_declaration", query_name + "_item", query_name):
                            type_node = type_node.parent
                        if type_node:
                            entity = self._create_entity_from_node(
                                type_node, content, entity_type, module_entity.id
                            )
                            if entity:
                                entities.append(entity)

        return entities

    @staticmethod
    def _capture(query, root) -> list[tuple]:
        """Run a query and return [(node, capture_name), ...].

        tree-sitter < 0.25 exposed Query.captures() returning (node, name)
        tuples. From 0.25 the query must be run through a QueryCursor, which
        returns a dict of capture name -> list of nodes.
        """
        if hasattr(query, "captures"):
            return list(query.captures(root))
        if _QueryCursor is None:
            return []
        cursor = _QueryCursor(query)
        captured = cursor.captures(root) or {}
        return [(node, name) for name, nodes in captured.items() for node in nodes]

    def _create_entity_from_node(
        self,
        node: tree_sitter.Node,
        content: str,
        entity_type: EntityType,
        parent_id: str,
        name_node: Optional[tree_sitter.Node] = None,
    ) -> Optional[Entity]:
        """Create entity from tree-sitter node."""
        # Find name node
        if name_node is None:
            for child in node.children:
                if child.type in ("identifier", "type_identifier", "property_identifier", "field_identifier"):
                    name_node = child
                    break

        if not name_node:
            return None

        name = content[name_node.start_byte:name_node.end_byte]
        qualified_name = f"{self._current_file.stem}.{name}"

        location = SourceLocation(
            file_path=str(self._current_file),
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            start_col=node.start_point[1],
            end_col=node.end_point[1],
        )

        signature = content[node.start_byte:node.end_byte]

        entity = Entity(
            id=generate_entity_id(
                qualified_name=qualified_name,
                entity_type=entity_type.value,
                file_path=str(self._current_file),
                language=self.language.value,
            ),
            name=name,
            qualified_name=qualified_name,
            entity_type=entity_type,
            language=self.language,
            location=location,
            signature=signature,
            parent_id=parent_id,
        )

        # Basic role classification
        entity.role = self._classify_role(entity, name)

        return entity

    def _classify_role(self, entity: Entity, name: str) -> EntityRole:
        """Basic role classification."""
        name_lower = name.lower()
        if name_lower.startswith("test_") or name_lower.endswith("_test"):
            return EntityRole.TEST
        if name_lower.startswith("_"):
            return EntityRole.INTERNAL
        # PROTOCOL is an EntityRole, not an EntityType - interfaces and traits
        # are the entity types that carry the protocol role.
        if entity.entity_type in (EntityType.INTERFACE, EntityType.TRAIT):
            return EntityRole.PROTOCOL
        if entity.parent_id is None:
            return EntityRole.PUBLIC_API
        return EntityRole.INTERNAL