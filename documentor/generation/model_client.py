"""Model clients for Nemotron inference."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass

from documentor.core.config import get_config
from documentor.core.logging import get_logger
from documentor.core.exceptions import ModelError, ModelNotAvailableError

logger = get_logger(__name__)


@dataclass
class ModelResponse:
    """Response from model inference."""
    content: str
    model: str
    tokens_used: int = 0
    latency_ms: int = 0


class ModelClient(ABC):
    """Abstract base class for model clients."""

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "", **kwargs) -> ModelResponse:
        """Generate text from prompt."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if model is available."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Get model name."""
        pass


class LocalModelClient(ModelClient):
    """Local Ollama model client."""

    def __init__(self, model_name: Optional[str] = None, base_url: str = "http://localhost:11434"):
        self._model_name = model_name or get_config().generation.model.local
        self._base_url = base_url
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        """Initialize Ollama client."""
        try:
            import ollama
            self._client = ollama.Client(host=self._base_url)
        except ImportError:
            logger.warning("Ollama not installed. Local inference unavailable.")

    @property
    def model_name(self) -> str:
        return self._model_name

    def is_available(self) -> bool:
        if not self._client:
            return False
        try:
            response = self._client.list()
            # Newer ollama clients return pydantic models, older ones dicts.
            if isinstance(response, dict):
                models = response.get("models", [])
            else:
                models = getattr(response, "models", []) or []
            for model in models:
                if isinstance(model, dict):
                    name = model.get("name") or model.get("model")
                else:
                    # ollama >= 0.5 renamed the field from `name` to `model`.
                    name = (getattr(model, "name", None)
                            or getattr(model, "model", None))
                if name and name.startswith(self._model_name):
                    return True
            return False
        except Exception:
            return False

    def generate(self, prompt: str, system_prompt: str = "", **kwargs) -> ModelResponse:
        if not self._client:
            raise ModelNotAvailableError(f"Ollama client not initialized for {self._model_name}")

        if not self.is_available():
            raise ModelNotAvailableError(f"Model {self._model_name} not available locally")

        import time
        start = time.time()

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = self._client.chat(
                model=self._model_name,
                messages=messages,
                options={
                    "temperature": kwargs.get("temperature", 0.1),
                    "num_predict": kwargs.get("max_tokens", 2000),
                },
            )

            latency = int((time.time() - start) * 1000)
            content = response["message"]["content"]

            return ModelResponse(
                content=content,
                model=self._model_name,
                latency_ms=latency,
            )

        except Exception as e:
            raise ModelError(f"Local generation failed: {e}") from e


class NebiusModelClient(ModelClient):
    """Nebius Serverless Endpoint model client."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ):
        self._model_name = model_name or get_config().generation.model.cloud
        self._api_key = api_key or get_config().nebius.api_key
        self._endpoint_url = endpoint_url or get_config().nebius.endpoint_url
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        """Initialize HTTP client."""
        import httpx
        if self._api_key and self._endpoint_url:
            self._client = httpx.Client(
                base_url=self._endpoint_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )

    @property
    def model_name(self) -> str:
        return self._model_name

    def is_available(self) -> bool:
        return self._client is not None and bool(self._api_key) and bool(self._endpoint_url)

    def generate(self, prompt: str, system_prompt: str = "", **kwargs) -> ModelResponse:
        if not self._client:
            raise ModelNotAvailableError("Nebius client not configured")

        import time
        import json
        start = time.time()

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": self._model_name,
                "messages": messages,
                "temperature": kwargs.get("temperature", 0.1),
                "max_tokens": kwargs.get("max_tokens", 2000),
            }

            response = self._client.post("/v1/chat/completions", json=payload)
            response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            tokens_used = data.get("usage", {}).get("total_tokens", 0)

            latency = int((time.time() - start) * 1000)

            return ModelResponse(
                content=content,
                model=self._model_name,
                tokens_used=tokens_used,
                latency_ms=latency,
            )

        except Exception as e:
            raise ModelError(f"Nebius generation failed: {e}") from e


class ModelRouter:
    """Routes requests to local or cloud model based on availability and config."""

    def __init__(self):
        self.config = get_config()
        self.local = LocalModelClient()
        self.cloud = NebiusModelClient()

    def generate(self, prompt: str, system_prompt: str = "", **kwargs) -> ModelResponse:
        """Generate using preferred model."""
        prefer_local = self.config.generation.model.prefer_local

        # Try preferred first
        if prefer_local and self.local.is_available():
            try:
                return self.local.generate(prompt, system_prompt, **kwargs)
            except Exception as e:
                logger.warning(f"Local model failed, falling back to cloud: {e}")

        if self.cloud.is_available():
            try:
                return self.cloud.generate(prompt, system_prompt, **kwargs)
            except Exception as e:
                logger.error(f"Cloud model failed: {e}")
                raise

        if not prefer_local and self.local.is_available():
            try:
                return self.local.generate(prompt, system_prompt, **kwargs)
            except Exception as e:
                logger.error(f"Local model failed: {e}")
                raise

        raise ModelNotAvailableError("No model available (local or cloud)")