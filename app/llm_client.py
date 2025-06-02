"""
LLM client abstraction layer to support multiple providers.

This module provides a unified interface for different LLM providers,
making it easy to switch between Ollama and OpenAI API while maintaining
the same interface for the rest of the application.
"""

from __future__ import annotations
import os
from typing import List, Dict, Any
from abc import ABC, abstractmethod

try:
    from ollama import chat as ollama_chat
except ImportError:
    ollama_chat = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class LLMResponse:
    """Unified response object for LLM responses."""
    
    def __init__(self, content: str):
        self.message = MessageContent(content)


class MessageContent:
    """Message content wrapper."""
    
    def __init__(self, content: str):
        self.content = content


class LLMClient(ABC):
    """Abstract base class for LLM clients."""
    
    @abstractmethod
    def chat(self, model: str, messages: List[Dict[str, str]]) -> LLMResponse:
        """Send a chat request to the LLM provider."""
        pass


class OllamaClient(LLMClient):
    """Ollama client implementation."""
    
    def __init__(self):
        if ollama_chat is None:
            raise ImportError("ollama package is required for OllamaClient")
    
    def chat(self, model: str, messages: List[Dict[str, str]]) -> LLMResponse:
        """Send a chat request to Ollama."""
        response = ollama_chat(model=model, messages=messages)
        return LLMResponse(response.message.content)


class OpenAIClient(LLMClient):
    """OpenAI client implementation."""
    
    def __init__(self, api_key: str | None = None):
        if OpenAI is None:
            raise ImportError("openai package is required for OpenAIClient")
        
        # Use provided API key or get from environment
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
        
        self.client = OpenAI(api_key=api_key)
    
    def chat(self, model: str, messages: List[Dict[str, str]]) -> LLMResponse:
        """Send a chat request to OpenAI."""
        # Map devstral to a suitable OpenAI model for backwards compatibility
        if model == "devstral":
            model = "gpt-4o-mini"  # Use gpt-4o-mini as a good default for code generation
        
        try:
            from config import OPENAI_MODEL_PARAMS
            temperature = OPENAI_MODEL_PARAMS.get("temperature", 0.7)
            max_tokens = OPENAI_MODEL_PARAMS.get("max_tokens", 4096)
        except ImportError:
            temperature = 0.7
            max_tokens = 4096
        
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return LLMResponse(response.choices[0].message.content)


def get_llm_client() -> LLMClient:
    """Factory function to get the appropriate LLM client based on configuration."""
    try:
        from config import LLM_PROVIDER
        provider = LLM_PROVIDER
    except ImportError:
        provider = os.getenv("LLM_PROVIDER", "openai").lower()
    
    if provider == "openai":
        return OpenAIClient()
    elif provider == "ollama":
        return OllamaClient()
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


# Create a global client instance
_llm_client = None

def chat(model: str, messages: List[Dict[str, str]]) -> LLMResponse:
    """
    Unified chat function that works with any configured LLM provider.
    
    This function maintains the same interface as the original ollama.chat
    function, making it a drop-in replacement.
    """
    global _llm_client
    if _llm_client is None:
        _llm_client = get_llm_client()
    
    return _llm_client.chat(model, messages)
