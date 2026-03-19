"""LLM client abstraction.

Provides a unified interface for calling language models:
- LLMClient: abstract base with generate() and generate_with_tools()
- ModelConfig: model name, temperature, max tokens
- Pre-configured presets for different roles (Master, major NPC, minor NPC)

Concrete implementations (e.g., OpenRouterClient) live here as well.
The client is injected into layers and the Master — they never create their own.
"""
