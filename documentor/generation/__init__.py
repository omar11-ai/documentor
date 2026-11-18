"""DocuMentor generation package."""

from documentor.generation.generator import DocumentationGenerator
from documentor.generation.prompts import (
    ENTITY_DOC_PROMPT,
    MODULE_DOC_PROMPT,
    CLASS_DOC_PROMPT,
    FUNCTION_DOC_PROMPT,
)
from documentor.generation.model_client import ModelClient, LocalModelClient, NebiusModelClient

__all__ = [
    "DocumentationGenerator",
    "ENTITY_DOC_PROMPT",
    "MODULE_DOC_PROMPT",
    "CLASS_DOC_PROMPT",
    "FUNCTION_DOC_PROMPT",
    "ModelClient",
    "LocalModelClient",
    "NebiusModelClient",
]