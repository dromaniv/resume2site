"""
Configuration settings for the resume2site application.

This file contains configuration for different LLM providers and models.
You can easily switch between providers by changing the settings here.
"""

from dotenv import load_dotenv
load_dotenv()          # ← must be before os.getenv(...)
import os

# LLM Provider Configuration
# Set to "ollama" or "openai"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # Changed default to OpenAI

# Model Configuration
# For Ollama: use models like "devstral", "llama2", etc.
# For OpenAI: use models like "gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo", etc.
DEFAULT_MODEL = {
    "ollama": "deepseek-coder-v2",
    "openai": "gpt-4o-mini"  # Good balance of performance and cost
}

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
OPENAI_MODEL_PARAMS = {
    "temperature": 0.7,
    "max_tokens": 4096
}

# Ollama Configuration  
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

def get_model_for_provider(provider: str = None) -> str:
    """Get the default model for the specified provider."""
    provider = provider or LLM_PROVIDER
    return DEFAULT_MODEL.get(provider, "gpt-4o-mini")
