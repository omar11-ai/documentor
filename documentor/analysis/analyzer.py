"""Codebase analyzer - orchestrates parsing and git analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from documentor.core.models import (
    KnowledgeGraph,
    Entity,
    Language,
    GitInfo,
)
from documentor.analysis.parser_base import BaseParser
from documentor.analysis.python_parser import PythonParser
from documentor.analysis.tree_sitter_parser import TreeSitterParser
from documentor.utils.file_utils import find_files, get_language_from_extension
from documentor.utils.git_utils import (
    get_repo_root,
    get_file_history,
    get_co_change_files,
)
from documentor.core.config import get_config
from documentor.core.logging import get_logger
from documentor.core.exceptions import AnalysisError

logger = get_logger(__name__)


@dataclass
class AnalysisResult:
    """Result of codebase analysis."""
    graph: KnowledgeGraph
    files_analyzed: int
    entities_found: int
    languages_detected: set[Language]
    errors: list[str]


class CodebaseAnalyzer:
    """Main analyzer for codebases."""

    def __init__(self, repo_path: Optional[Path] = None):
        self.repo_path = repo_path or Path.cwd()
        self.config = get_config()
        self.parsers: dict[Language, BaseParser] = {
            Language.PYTHON: PythonParser(Language.PYTHON),
        }
        # Try to initialize tree-sitter parsers
        for lang in [Language.JAVASCRIPT, Language.TYPESCRIPT, Language.GO, Language.RUST]:
            try:
                parser = TreeSitterParser(lang)
                if parser._parser:
                    self.parsers[lang] = parser
            except Exception:
                pass

    def analyze(self) -> AnalysisResult:
        """Run full codebase analysis."""
        logger.info(f"Analyzing codebase at {self.repo_path}")

        # Find files to analyze
        files = find_files(
            self.repo_path,
            self.config.analysis.include_patterns,
            self.config.analysis.exclude_patterns,
        )

        logger.info(f"Found {len(files)} files to analyze")

        # Group files by language
        files_by_lang: dict[Language, list[Path]] = {}
        for file_path in files:
            lang = get_language_from_extension(file_path)
            if lang and Language(lang) in self.parsers:
                files_by_lang.setdefault(Language(lang), []).append(file_path)

        # Parse files
        combined_graph = KnowledgeGraph()
        errors = []
        total_entities = 0

        for lang, lang_files in files_by_lang.items():
            parser = self.parsers[lang]
            try:
                logger.info(f"Parsing {len(lang_files)} {lang.value} files...")
                graph = parser.parse_files(lang_files)
                # Merge graphs
                for entity_id, entity in graph.entities.items():
                    combined_graph.add_entity(entity)
                for rel in graph.relationships:
                    combined_graph.add_relationship(rel)
                total_entities += len(graph.entities)
            except Exception as e:
                error_msg = f"Failed to parse {lang.value} files: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Run git analysis
        if self.config.analysis.include_patterns:  # Only if git analysis enabled
            self._enrich_with_git(combined_graph)

        languages_detected = set(files_by_lang.keys())

        result = AnalysisResult(
            graph=combined_graph,
            files_analyzed=len(files),
            entities_found=total_entities,
            languages_detected=languages_detected,
            errors=errors,
        )

        logger.info(
            f"Analysis complete: {result.files_analyzed} files, "
            f"{result.entities_found} entities, {len(languages_detected)} languages"
        )

        return result

    def _enrich_with_git(self, graph: KnowledgeGraph) -> None:
        """Enrich entities with git history information."""
        logger.info("Enriching with git history...")

        try:
            repo_root = get_repo_root(self.repo_path)
        except Exception:
            logger.warning("Not a git repository, skipping git analysis")
            return

        for entity in graph.entities.values():
            try:
                file_path = Path(entity.location.file_path)
                if not file_path.is_absolute():
                    file_path = repo_root / file_path

                if not file_path.exists():
                    continue

                # Get file history
                history = get_file_history(repo_root, file_path, max_count=50)
                if not history:
                    continue

                co_changes = get_co_change_files(repo_root, file_path)

                # Determine first/last commit
                first_commit = history[-1].hash if history else ""
                last_commit = history[0].hash if history else ""

                bug_fixes = [c.hash for c in history if c.is_bug_fix]
                features = [c.hash for c in history if c.is_feature]

                git_info = GitInfo(
                    file_path=str(file_path.relative_to(repo_root)),
                    first_commit=first_commit,
                    last_commit=last_commit,
                    commit_count=len(history),
                    author_count=len(set(c.author for c in history)),
                    last_modified=history[0].date if history else None,
                    recent_changes=history[:10],
                    co_change_files=co_changes,
                    bug_fix_commits=bug_fixes,
                    feature_commits=features,
                )

                entity.git_info = git_info

            except Exception as e:
                logger.debug(f"Failed to get git info for {entity.id}: {e}")

    def analyze_incremental(self, changed_files: list[Path]) -> KnowledgeGraph:
        """Analyze only changed files (for watch mode)."""
        logger.info(f"Incremental analysis for {len(changed_files)} files")

        # Group by language
        files_by_lang: dict[Language, list[Path]] = {}
        for file_path in changed_files:
            lang = get_language_from_extension(file_path)
            if lang and Language(lang) in self.parsers:
                files_by_lang.setdefault(Language(lang), []).append(file_path)

        # Parse changed files
        new_graph = KnowledgeGraph()
        for lang, lang_files in files_by_lang.items():
            parser = self.parsers[lang]
            try:
                graph = parser.parse_files(lang_files)
                for entity_id, entity in graph.entities.items():
                    new_graph.add_entity(entity)
                for rel in graph.relationships:
                    new_graph.add_relationship(rel)
            except Exception as e:
                logger.error(f"Failed to parse {lang.value} files: {e}")

        return new_graph