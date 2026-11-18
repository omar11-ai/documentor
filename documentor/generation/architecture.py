"""Repository-level architecture documentation.

Most documentation generators describe one file or one symbol at a time.
This module produces the page a maintainer actually reads first: how the
repository is laid out, which modules carry the weight, and - from the git
history - which parts of it churn.

The context is assembled from facts the analyzer already extracted (AST
entities, file paths, git statistics), so the narrative the model writes is
grounded in the repository rather than invented.
"""

from __future__ import annotations

import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from documentor.core.models import Entity, EntityType, KnowledgeGraph


def _relative(path: str, root: Optional[str]) -> str:
    """Make an absolute source path relative to the repository root."""
    if not path:
        return path
    if root:
        try:
            rel = os.path.relpath(path, root)
            if not rel.startswith(".."):
                return rel.replace(os.sep, "/")
        except (ValueError, OSError):
            pass
    return Path(path).name


def _repo_root(graph: KnowledgeGraph) -> Optional[str]:
    """Longest common directory of every analysed file."""
    paths = [
        e.location.file_path
        for e in graph.entities.values()
        if e.location and e.location.file_path
    ]
    if not paths:
        return None
    if len(paths) == 1:
        return os.path.dirname(paths[0])

    common = os.path.commonpath(paths)
    # The common path of the files is usually a subdirectory (src/, app/);
    # step up until it looks like the repository root.
    parts = common.replace("\\", "/").split("/")
    while len(parts) > 1 and parts[-1] in (
        "src", "lib", "app", "source", "packages", "internal", "pkg",
    ):
        common = os.path.dirname(common)
        parts = common.replace("\\", "/").split("/")
    return common


def build_architecture_context(
    graph: KnowledgeGraph,
    project_name: str = "the project",
) -> dict:
    """Collect the facts the architecture page is built from."""
    root = _repo_root(graph)

    modules: dict[str, Entity] = {}
    entity_types: Counter[str] = Counter()
    languages: Counter[str] = Counter()
    files_by_dir: dict[str, set[str]] = defaultdict(set)
    public_api: list[str] = []

    for entity in graph.entities.values():
        languages[entity.language.value] += 1
        if entity.entity_type == EntityType.MODULE:
            modules[entity.name] = entity
            rel = _relative(entity.location.file_path, root)
            parts = rel.split("/")
            directory = "/".join(parts[:-1]) if len(parts) > 1 else "."
            files_by_dir[directory].add(parts[-1])
            continue

        entity_types[entity.entity_type.value] += 1
        if entity.role.value in ("public_api", "entry_point"):
            public_api.append(entity.qualified_name)

    module_rows = []
    for name, module in modules.items():
        module_rows.append({
            "name": name,
            "path": _relative(module.location.file_path, root),
            "commits": module.git_info.commit_count if module.git_info else 0,
            "authors": module.git_info.author_count if module.git_info else 0,
            "bugs": len(module.git_info.bug_fix_commits) if module.git_info else 0,
        })
    module_rows.sort(key=lambda r: (-r["commits"], r["name"]))

    bug_messages: list[str] = []
    feature_count = 0
    total_commits = 0
    total_authors = 0
    for module in modules.values():
        if not module.git_info:
            continue
        total_commits += module.git_info.commit_count
        total_authors += module.git_info.author_count
        feature_count += len(module.git_info.feature_commits)
        for message in module.git_info.bug_fix_commits[:3]:
            if message not in bug_messages:
                bug_messages.append(message)

    return {
        "project_name": project_name,
        "root": root,
        "module_count": len(modules),
        "entity_count": sum(entity_types.values()),
        "languages": dict(languages),
        "entity_types": dict(entity_types),
        "directories": {d: sorted(f) for d, f in sorted(files_by_dir.items())},
        "modules": module_rows,
        "hotspots": module_rows[:12],
        "public_api": sorted(public_api)[:25],
        "total_commits": total_commits,
        "total_authors": total_authors,
        "bug_fix_count": len(bug_messages),
        "feature_count": feature_count,
        "bug_messages": bug_messages[:12],
    }


def format_context(context: dict) -> str:
    """Render the context as the facts block the model is given."""
    lines = [f"Project: {context['project_name']}"]
    lines.append(
        f"Languages: {', '.join(f'{k} ({v} entities)' for k, v in context['languages'].items()) or 'unknown'}"
    )
    lines.append(
        f"Size: {context['module_count']} modules, {context['entity_count']} entities"
    )
    lines.append(f"Entity kinds: {context['entity_types']}")
    lines.append(
        f"Git: {context['total_commits']} commits by {context['total_authors']} authors, "
        f"{context['bug_fix_count']} bug-fix commits, {context['feature_count']} feature commits"
    )

    lines.append("\nDirectory layout (file counts by directory):")
    for directory, files in context["directories"].items():
        lines.append(f"  {directory}/  ({len(files)} files)")

    lines.append("\nModules, busiest first (name | path | commits | bug fixes):")
    for row in context["modules"][:40]:
        lines.append(
            f"  {row['name']} | {row['path']} | {row['commits']} commits | {row['bugs']} bug fixes"
        )
    if len(context["modules"]) > 40:
        lines.append(f"  ... and {len(context['modules']) - 40} more")

    if context["public_api"]:
        lines.append("\nPublic API surface (sample):")
        for name in context["public_api"]:
            lines.append(f"  {name}")

    if context["bug_messages"]:
        lines.append("\nRecent bug-fix commits (these are the areas that broke):")
        for message in context["bug_messages"]:
            lines.append(f"  {message}")

    return "\n".join(lines)


def render_architecture_fallback(context: dict) -> str:
    """Deterministic architecture page, used when no model is available."""
    lines = [
        f"# Architecture: {context['project_name']}",
        "",
        "> _Generated offline from static analysis (no LLM available)._",
        "",
        f"- **Modules:** {context['module_count']}",
        f"- **Entities:** {context['entity_count']}",
        f"- **Languages:** {', '.join(context['languages']) or 'unknown'}",
        f"- **Commits analysed:** {context['total_commits']} "
        f"by {context['total_authors']} authors",
        "",
        "## Directory layout",
        "",
        "```",
    ]
    for directory, files in context["directories"].items():
        lines.append(f"{directory}/")
        for f in files:
            lines.append(f"  {f}")
    lines.append("```")

    lines += ["", "## Modules by commit count", "",
              "| Module | File | Commits | Authors | Bug fixes |",
              "|---|---|---|---|---|"]
    for row in context["modules"][:60]:
        lines.append(
            f"| `{row['name']}` | `{row['path']}` | {row['commits']} | "
            f"{row['authors']} | {row['bugs']} |"
        )

    if context["bug_messages"]:
        lines += ["", "## Bug-fix history", "",
                  "These commits fixed defects, so they mark the areas that "
                  "have broken before:", ""]
        for message in context["bug_messages"]:
            lines.append(f"- {message}")

    return "\n".join(lines)


ARCHITECTURE_PROMPT = """You are writing the architecture page for the \
repository "{project_name}".

Below are facts extracted mechanically from the repository: the directory \
layout, the modules with their file paths and commit counts, the public API \
surface, and the bug-fix commits from the git history.

Write a concise architecture overview in Markdown. Use only the facts given \
below - do not invent features, frameworks, or file paths. If something is not \
in the facts, leave it out.

Structure it like this:

# Architecture: {project_name}

## What this project is
Two or three sentences, grounded in the module names and entity kinds.

## How it is laid out
Describe the directory structure and what each area appears to hold.

## Key modules
A table of the 15 modules that matter most, with what each one appears to do \
and its commit count. Pick the modules the numbers point to: the most \
committed-to, or the most bug-fixes. Do not list more than 15 rows.

## Public API surface
The exported entry points, and what they suggest about how the project is \
meant to be used.

## Hotspots and gotchas
The modules with the highest churn and the bug-fix commits. Say plainly \
which parts of this codebase have broken before, because that is where a \
new contributor will get stuck.

FACTS:
{facts}
"""


def build_architecture_prompt(context: dict) -> str:
    return ARCHITECTURE_PROMPT.format(
        project_name=context["project_name"],
        facts=format_context(context),
    )
