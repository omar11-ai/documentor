"""Prompts for documentation generation."""

from __future__ import annotations

# System prompt for all documentation generation
SYSTEM_PROMPT = """You are an expert technical writer and software architect. Your task is to generate clear, accurate, and useful documentation for code entities based on their source code, context, and git history.

Guidelines:
- Explain WHAT the entity does, WHY it exists, and WHEN to use it
- Include practical usage examples when relevant
- Document parameters, return values, and side effects with semantic descriptions (not just types)
- Note any "gotchas", edge cases, or common mistakes
- Reference related entities (callers, callees, alternatives)
- Mention stability (stable/experimental/deprecated) if known
- Keep it concise but complete - aim for 50-200 words per entity
- Write for developers who will actually use this code
- Use markdown formatting with clear sections"""

# Module documentation prompt
MODULE_DOC_PROMPT = """Generate documentation for this Python module.

Module: {qualified_name}
File: {file_path}

Source code:
```python
{source_code}
```

Docstring: {docstring}

Git history:
- Commits: {commit_count}
- Authors: {author_count}
- Recent changes: {recent_changes_summary}
- Bug fixes: {bug_fix_count}
- Features: {feature_count}

Public entities in this module:
{entities_summary}

Generate a module-level documentation with these sections:
## Overview
Brief description of the module's purpose and main responsibilities.

## Key Components
List the main classes/functions with one-line descriptions.

## Usage Example
A practical example showing how to use this module.

## Related Modules
Other modules this one interacts with (from imports/co-changes).

## Stability
Stability assessment based on git history."""

# Class documentation prompt
CLASS_DOC_PROMPT = """Generate documentation for this class.

Class: {qualified_name}
File: {file_path}
Line: {start_line}-{end_line}

Source code:
```python
{source_code}
```

Docstring: {docstring}

Parent: {parent_name}
Methods: {methods_summary}
Inherits from: {bases}

Git history:
- Commits: {commit_count}
- Recent changes: {recent_changes_summary}
- Bug fixes: {bug_fix_count}

Callers: {callers_summary}
Callees: {callees_summary}

Generate class documentation with these sections:
## Purpose
What this class represents and why it exists.

## When to Use
Scenarios where this class is the right choice.

## Constructor
Parameters and initialization behavior.

## Key Methods
Most important public methods with brief descriptions.

## Usage Example
```python
# Concrete example
```

## Gotchas
Edge cases, common mistakes, or limitations.

## Related
Other classes/functions to consider."""

# Function/Method documentation prompt
FUNCTION_DOC_PROMPT = """Generate documentation for this function/method.

Function: {qualified_name}
Type: {entity_type}
File: {file_path}
Line: {start_line}-{end_line}

Signature:
```python
{signature}
```

Source code:
```python
{source_code}
```

Docstring: {docstring}

Parent: {parent_name}

Git history:
- Commits: {commit_count}
- Recent changes: {recent_changes_summary}
- Bug fixes: {bug_fix_count}

Calls: {calls_summary}
Called by: {callers_summary}

Generate function documentation with these sections:
## Purpose
What this function does and why it exists.

## Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| ... | ... | ... |

## Returns
| Type | Description |
|------|-------------|
| ... | ... |

## Side Effects
Any mutations, I/O, or state changes.

## Usage Example
```python
# Concrete example
```

## Gotchas
Edge cases, preconditions, or common mistakes.

## See Also
Related functions."""

# Generic entity documentation prompt
ENTITY_DOC_PROMPT = """Generate documentation for this code entity.

Entity: {qualified_name}
Type: {entity_type}
Language: {language}
File: {file_path}
Line: {start_line}-{end_line}

Signature:
```
{signature}
```

Source code:
```
{source_code}
```

Docstring: {docstring}

Context:
- Parent: {parent_name}
- Children: {children_summary}
- Imports: {imports_summary}
- Calls: {calls_summary}
- Called by: {callers_summary}

Git history:
- Commits: {commit_count}
- Authors: {author_count}
- Recent changes: {recent_changes_summary}
- Bug fixes: {bug_fix_count}
- Features: {feature_count}

Generate documentation with these sections:
## Purpose
What this entity does and why it exists.

## When to Use
Practical scenarios for using this entity.

## Interface
Key methods/properties/parameters with descriptions.

## Example
```{language}
# Concrete usage example
```

## Notes
Gotchas, limitations, or important considerations.

## Related
Other relevant entities."""