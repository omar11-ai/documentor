"""Offline template fallback for documentation generation.

Used when no LLM (Ollama/Nebius) is available. Produces deterministic,
useful Markdown from the knowledge graph so the pipeline, web UI, and
demo remain functional without credentials.
"""

from __future__ import annotations

from pathlib import Path

from documentor.core.models import Entity, EntityType


def render_entity_doc(
    entity: Entity,
    source_snippet: str = "",
    callers: str = "None",
    callees: str = "None",
) -> str:
    """Render deterministic Markdown for a single entity."""
    git_lines = ["- No git history available"]
    if entity.git_info:
        g = entity.git_info
        git_lines = [
            f"- Commits: {g.commit_count}",
            f"- Authors: {g.author_count}",
            f"- Bug fixes: {len(g.bug_fix_commits)}",
            f"- Features: {len(g.feature_commits)}",
        ]
    git_section = "\n".join(git_lines)

    docstring = entity.docstring or "_No docstring provided._"
    signature = entity.signature or "N/A"
    snippet_block = f"```\n{source_snippet}\n```" if source_snippet else "_Source unavailable._"

    return f"""# {entity.qualified_name}

> _Generated offline from static analysis (no LLM available). Connect Ollama/Nebius for AI-enhanced narrative docs._

- **Type:** {entity.entity_type.value}
- **Language:** {entity.language.value}
- **File:** `{entity.location.file_path}` (lines {entity.location.start_line}-{entity.location.end_line})
- **Role:** {entity.role.value}
- **Stability:** {entity.stability.value}

## Signature

```
{signature}
```

## Docstring

{docstring}

## Source

{snippet_block}

## Git History

{git_section}

## Callers

{callers}

## Callees

{callees}
"""


def render_module_doc(
    module: Entity,
    entities: list[Entity],
    source_snippet: str = "",
) -> str:
    """Render deterministic Markdown for a module."""
    public = [e for e in entities if e.role.value in ("public_api", "entry_point")]
    if public:
        rows = "\n".join(
            f"| `{e.qualified_name}` | {e.entity_type.value} | {(e.docstring or 'No description').splitlines()[0][:80]} |"
            for e in public[:20]
        )
    else:
        all_rows = "\n".join(
            f"| `{e.qualified_name}` | {e.entity_type.value} | {(e.docstring or 'No description').splitlines()[0][:80]} |"
            for e in entities[:20]
        )
        rows = all_rows if all_rows else "| _none_ | — | — |"

    git_section = "- No git history available"
    if module.git_info:
        g = module.git_info
        git_section = (
            f"- Commits: {g.commit_count}\n"
            f"- Authors: {g.author_count}\n"
            f"- Bug fixes: {len(g.bug_fix_commits)}\n"
            f"- Features: {len(g.feature_commits)}"
        )

    snippet = f"\n```\n{source_snippet[:2000]}\n```\n" if source_snippet else ""

    return f"""# Module: {module.qualified_name}

> _Generated offline from static analysis (no LLM available)._

**File:** `{module.location.file_path}`

## Overview

Module `{module.qualified_name}` contains {len(entities)} analyzed entities.
{snippet}
## Key Components

| Entity | Type | Description |
|--------|------|-------------|
{rows}

## Git History

{git_section}

## Note

Connect an NVIDIA Nemotron model (Ollama locally or Nebius Serverless) and re-run
`documentor generate` to upgrade these pages to AI-generated narrative docs with
purpose, usage examples, and gotchas.
"""


def is_llm_doc(content: str) -> bool:
    """Check whether content came from the offline fallback."""
    return "Generated offline from static analysis" not in content


def module_key_for_entity(entity: Entity) -> str:
    """Module key used to group entity docs on disk."""
    if entity.entity_type == EntityType.MODULE:
        return entity.name
    return Path(entity.location.file_path).stem
