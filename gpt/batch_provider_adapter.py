from config.config_loader import get_config
from .gemini_provider import GeminiProvider
from .deepseek_provider import DeepSeekProvider
from .mocks.mock_provider import MockProvider


def get_provider(name: str, config: dict = None):
    """Return a ProviderBase instance for the given provider name.

    ``config`` should be the provider-specific sub-dict (e.g.
    ``full_config["ai"]["gemini"]``), not the full config tree.
    """
    name = (name or "").lower()
    if name in ("gemini", "anthropic_gemini"):
        return GeminiProvider(config)
    if name == "deepseek":
        return DeepSeekProvider(config)
    if name in ("mock", "mockprovider"):
        return MockProvider(config)
    raise ValueError(f"Unknown provider for ProviderBase adapter: {name!r}")


def get_provider_instance():
    """Return a ProviderBase instance configured from config.yaml + env vars."""
    cfg = get_config()
    provider_name = cfg.get("ai", {}).get("provider", "mock").lower()
    # Pass the provider-specific sub-config so api_key / model etc. are available
    provider_cfg = cfg.get("ai", {}).get(provider_name, {})
    return get_provider(provider_name, provider_cfg)
