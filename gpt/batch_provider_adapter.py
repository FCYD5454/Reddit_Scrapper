from config.config_loader import get_config
from .gemini_provider import GeminiProvider
from .deepseek_provider import DeepSeekProvider
from .mocks.mock_provider import MockProvider

def get_provider(name: str, config: dict = None):
    name = (name or "").lower()
    if name in ("gemini", "anthropic_gemini"):
        return GeminiProvider(config)
    if name == "deepseek":
        return DeepSeekProvider(config)
    if name in ("mock", "mockprovider"):
        return MockProvider(config)
    # optional fallback
    raise ValueError(f"Unknown provider: {name}")

def get_provider_instance():
    cfg = get_config()
    provider_name = cfg.get("ai", {}).get("provider", "mock").lower()
    return get_provider(provider_name, cfg)