from langchain_openai import ChatOpenAI

from ipilot.config.schema import Config

def build_chat_model(config: Config):
    provider_name = config.agents.defaults.provider
    provider_config = getattr(config.providers, provider_name)

    return ChatOpenAI(
        model=config.agents.defaults.model,
        api_key=provider_config.api_key,
        base_url=provider_config.api_base,
        temperature=config.agents.defaults.temperature,
    )
