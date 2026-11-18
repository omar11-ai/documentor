"""Configuration management for DocuMentor."""

from pathlib import Path
from typing import Literal, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProjectConfig(BaseSettings):
    name: str = "my-project"
    languages: list[Literal["python", "javascript", "typescript", "go", "rust"]] = ["python"]


class AnalysisConfig(BaseSettings):
    include_patterns: list[str] = ["**/*.py"]
    exclude_patterns: list[str] = [
        "**/test*.py",
        "**/*_test.py",
        "**/tests/**",
        "**/migrations/**",
        "**/.venv/**",
        "**/venv/**",
        "**/__pycache__/**",
        "**/node_modules/**",
        "**/target/**",
        "**/.git/**",
    ]
    max_file_size_mb: int = 10


class ModelConfig(BaseSettings):
    local: str = "nemotron-mini"
    cloud: str = "nemotron-3-ultra"
    prefer_local: bool = True
    timeout_seconds: int = 120
    max_retries: int = 3


class GenerationConfig(BaseSettings):
    model: ModelConfig = Field(default_factory=ModelConfig)
    output_format: Literal["markdown", "html", "openapi"] = "markdown"
    include_private: bool = False
    include_tests: bool = False
    max_tokens_per_entity: int = 2000
    temperature: float = 0.1

    # Which documents the LLM writes.
    #
    # Module docs are architecture overviews - prose is the point, and the
    # model sees the whole module's entity list, so it stays factual.
    #
    # Per-entity docs are API references. Their value is the extracted
    # signature, role, stability and source, all of which come from the AST
    # and cannot drift. An LLM retelling the same thing can, so the LLM path
    # is opt-in for entities.
    llm_module_docs: bool = True
    llm_entity_docs: bool = False


class NebiusConfig(BaseSettings):
    api_key: Optional[str] = None
    endpoint_url: Optional[str] = None
    organization: Optional[str] = None


class ServerConfig(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8080
    reload: bool = False


class CacheConfig(BaseSettings):
    directory: Path = Path(".documentor_cache")
    embedding_model: str = "all-MiniLM-L6-v2"
    chroma_path: Path = Path(".chroma_db")


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        yaml_file=".documentor.yaml",
        yaml_file_encoding="utf-8",
        env_prefix="DOCUMENTOR_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    project: ProjectConfig = Field(default_factory=ProjectConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    nebius: NebiusConfig = Field(default_factory=NebiusConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)

    @field_validator("cache", "analysis", "generation", "nebius", "server", "project", mode="before")
    @classmethod
    def _coerce_dict(cls, v):
        if isinstance(v, dict):
            return v
        return v

    def save(self, path: Path = Path(".documentor.yaml")) -> None:
        """Save configuration to YAML file."""
        import yaml
        data = self.model_dump(mode="json")
        path.write_text(yaml.dump(data, sort_keys=False, default_flow_style=False))

    @classmethod
    def load(cls, path: Path = Path(".documentor.yaml")) -> "Config":
        """Load configuration from YAML file."""
        if path.exists():
            import yaml
            data = yaml.safe_load(path.read_text()) or {}
            return cls(**data)
        return cls()

    @classmethod
    def create_default(cls, path: Path = Path(".documentor.yaml")) -> "Config":
        """Create and save default configuration."""
        config = cls()
        config.save(path)
        return config


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get global configuration instance."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def set_config(config: Config) -> None:
    """Set global configuration instance."""
    global _config
    _config = config