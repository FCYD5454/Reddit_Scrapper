from config.config_loader import get_config

def get_provider_instance():
    cfg = get_config()
    provider = cfg.get(\"ai\", {}).get(\"provider\", \"openai\").lower()
    if provider == \"gemini\":
        from .gemini_batch import GeminiProvider
        return GeminiProvider(cfg)
    if provider == \"deepseek\":
        from .deepseek_batch import DeepSeekProvider  # optional file if you implement it
        return DeepSeekProvider(cfg)
    # fallback to existing openai provider if present
    try:
        from .openai_batch import OpenAIProvider
        return OpenAIProvider(cfg)
    except Exception:
        # If no OpenAI provider present, raise an informative error
        raise RuntimeError(\"No supported AI provider implementation found. Check ai.provider in config.\")

