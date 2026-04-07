from ipilot.config.schema import Config


def build_chat_model(config: Config):
    try:
        from langchain_openai import ChatOpenAI
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "langchain_openai is required to build the chat model. "
            "Install project dependencies or run the code in the synced project environment."
        ) from exc

    provider_name = config.agents.defaults.provider
    provider_config = getattr(config.providers, provider_name)

    return ChatOpenAI(
        model=config.agents.defaults.model,
        api_key=provider_config.api_key,
        base_url=provider_config.api_base,
        temperature=config.agents.defaults.temperature,
    )
