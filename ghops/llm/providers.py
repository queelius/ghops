"""
LLM provider implementations.

Supports multiple LLM providers with a unified interface:
- Ollama (local and remote)
- OpenAI (GPT-4, GPT-3.5)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import os
import logging

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate content from a prompt.

        Args:
            prompt: The input prompt
            **kwargs: Provider-specific options (temperature, max_tokens, etc.)

        Returns:
            Generated text content
        """
        pass

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """
        Get information about this provider.

        Returns:
            Dict with provider details (name, model, endpoint, cost, etc.)
        """
        pass

    def supports_streaming(self) -> bool:
        """Whether this provider supports streaming responses."""
        return False


class OllamaProvider(LLMProvider):
    """
    Ollama provider - supports local and remote endpoints.

    Ollama is a local LLM runner that supports models like:
    - llama3.2, llama3.1, llama3
    - mistral, mixtral
    - codellama, deepseek-coder
    - qwen2.5

    Can connect to remote Ollama instances via base_url.
    """

    def __init__(self,
                 base_url: str = "http://localhost:11434",
                 model: str = "llama3.2",
                 verify_ssl: bool = True):
        """
        Initialize Ollama provider.

        Args:
            base_url: Ollama API endpoint (local or remote)
            model: Model name (must be pulled on Ollama server)
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.verify_ssl = verify_ssl

        # Verify connection
        self._verify_connection()

    def _verify_connection(self):
        """Verify we can connect to Ollama."""
        try:
            import requests
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5,
                verify=self.verify_ssl
            )
            response.raise_for_status()

            # Check if model is available
            models = response.json().get('models', [])
            model_names = [m['name'] for m in models]

            if self.model not in model_names and f"{self.model}:latest" not in model_names:
                logger.warning(
                    f"Model '{self.model}' not found in Ollama. "
                    f"Available models: {', '.join(model_names)}"
                )
        except Exception as e:
            logger.error(f"Failed to connect to Ollama at {self.base_url}: {e}")
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                f"Is Ollama running? Error: {e}"
            )

    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate content using Ollama.

        Args:
            prompt: The input prompt
            **kwargs: Options:
                - temperature: float (0.0-2.0, default 0.7)
                - max_tokens: int (default 4000)
                - timeout: int (seconds, default 300)
                - system_prompt: str (optional system message)

        Returns:
            Generated text
        """
        import requests

        # Build request
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get('temperature', 0.7),
                "num_predict": kwargs.get('max_tokens', 4000),
            }
        }

        # Add system prompt if provided
        if 'system_prompt' in kwargs:
            payload['system'] = kwargs['system_prompt']

        # Make request
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=kwargs.get('timeout', 300),
                verify=self.verify_ssl
            )
            response.raise_for_status()

            result = response.json()
            return result['response']

        except requests.exceptions.Timeout:
            raise TimeoutError(
                f"Ollama generation timed out after {kwargs.get('timeout', 300)}s. "
                "Try increasing timeout or using a smaller model."
            )
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Ollama API error: {e}")

    def get_info(self) -> Dict[str, Any]:
        """Get provider information."""
        return {
            'provider': 'ollama',
            'base_url': self.base_url,
            'model': self.model,
            'cost': 0.0,  # Free for Ollama
            'supports_streaming': False
        }

    def __repr__(self):
        return f"OllamaProvider(base_url='{self.base_url}', model='{self.model}')"


class OpenAIProvider(LLMProvider):
    """
    OpenAI provider for GPT models.

    Supports:
    - gpt-4-turbo-preview
    - gpt-4
    - gpt-3.5-turbo

    Requires OPENAI_API_KEY environment variable or api_key parameter.
    """

    def __init__(self,
                 api_key: Optional[str] = None,
                 model: str = "gpt-4-turbo-preview"):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key (or use OPENAI_API_KEY env var)
            model: Model name
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "OpenAI package not installed. "
                "Install with: pip install openai"
            )

        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. "
                "Set OPENAI_API_KEY environment variable or pass api_key parameter."
            )

        self.model = model
        self.client = OpenAI(api_key=self.api_key)

    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate content using OpenAI.

        Args:
            prompt: The input prompt
            **kwargs: Options:
                - temperature: float (0.0-2.0, default 0.7)
                - max_tokens: int (default 4000)
                - system_prompt: str (default: technical writer)

        Returns:
            Generated text
        """
        system_prompt = kwargs.get(
            'system_prompt',
            "You are a technical writer creating engaging blog posts about software projects."
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=kwargs.get('temperature', 0.7),
                max_tokens=kwargs.get('max_tokens', 4000)
            )

            return response.choices[0].message.content

        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {e}")

    def get_info(self) -> Dict[str, Any]:
        """Get provider information."""
        # Approximate costs per 1K tokens
        costs = {
            'gpt-4-turbo-preview': {'input': 0.01, 'output': 0.03},
            'gpt-4': {'input': 0.03, 'output': 0.06},
            'gpt-3.5-turbo': {'input': 0.001, 'output': 0.002}
        }

        return {
            'provider': 'openai',
            'model': self.model,
            'cost_per_1k_tokens': costs.get(self.model, {'input': 'varies', 'output': 'varies'}),
            'supports_streaming': True
        }

    def __repr__(self):
        return f"OpenAIProvider(model='{self.model}')"


def get_llm_provider(config: Dict[str, Any]) -> LLMProvider:
    """
    Factory function to get configured LLM provider.

    Args:
        config: Configuration dict with llm settings

    Returns:
        Configured LLM provider instance

    Example config:
        {
            "llm": {
                "default_provider": "ollama",
                "providers": {
                    "ollama": {
                        "base_url": "http://localhost:11434",
                        "model": "llama3.2"
                    },
                    "openai": {
                        "api_key": "sk-...",
                        "model": "gpt-4-turbo-preview"
                    }
                }
            }
        }
    """
    llm_config = config.get('llm', {})

    if not llm_config:
        raise ValueError(
            "LLM not configured. Add 'llm' section to config with provider settings."
        )

    provider_name = llm_config.get('default_provider', 'ollama')
    provider_config = llm_config.get('providers', {}).get(provider_name, {})

    if provider_name == 'ollama':
        return OllamaProvider(
            base_url=provider_config.get('base_url', 'http://localhost:11434'),
            model=provider_config.get('model', 'llama3.2'),
            verify_ssl=provider_config.get('verify_ssl', True)
        )

    elif provider_name == 'openai':
        return OpenAIProvider(
            api_key=provider_config.get('api_key'),
            model=provider_config.get('model', 'gpt-4-turbo-preview')
        )

    else:
        raise ValueError(
            f"Unknown LLM provider: {provider_name}. "
            f"Supported providers: ollama, openai"
        )
