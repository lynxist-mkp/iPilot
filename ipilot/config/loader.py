from __future__ import annotations

import os

from ipilot.config.paths import get_config_path
from ipilot.config.schema import Config


TWITCH_ENV_OVERRIDES = {
    "enabled": ("IPILOT_TWITCH_ENABLED",),
    "client_id": ("IPILOT_TWITCH_CLIENT_ID",),
    "access_token": ("IPILOT_TWITCH_ACCESS_TOKEN",),
    "broadcaster_id": ("IPILOT_TWITCH_BROADCASTER_ID",),
    "sender_id": ("IPILOT_TWITCH_SENDER_ID",),
    "eventsub_ws_url": ("IPILOT_TWITCH_EVENTSUB_WS_URL",),
    "helix_api_base": ("IPILOT_TWITCH_HELIX_API_BASE",),
}


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _apply_env_overrides(config: Config) -> Config:
    payload = config.model_dump()
    twitch_config = payload.setdefault("channels", {}).setdefault("twitch", {})

    for field_name, env_names in TWITCH_ENV_OVERRIDES.items():
        raw_value = None
        for env_name in env_names:
            raw_value = os.getenv(env_name)
            if raw_value is not None:
                break
        if raw_value is None:
            continue
        twitch_config[field_name] = _parse_bool(raw_value) if field_name == "enabled" else raw_value

    return Config.model_validate(payload)


def load_config() -> Config:
    path = get_config_path()
    if not path.exists():
        return _apply_env_overrides(Config())
    return _apply_env_overrides(Config.model_validate_json(path.read_text(encoding="utf-8")))


def save_config(config: Config) -> None:
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")

