from __future__ import annotations

from ipilot.config.loader import load_config, save_config
from ipilot.config.schema import Config


def test_load_config_applies_twitch_environment_overrides(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr("ipilot.config.loader.get_config_path", lambda: config_path)
    save_config(
        Config(
            channels={
                "twitch": {
                    "enabled": False,
                    "client_id": "from-config",
                    "access_token": "from-config-token",
                }
            }
        )
    )
    monkeypatch.setenv("IPILOT_TWITCH_ENABLED", "true")
    monkeypatch.setenv("IPILOT_TWITCH_CLIENT_ID", "from-env")
    monkeypatch.setenv("IPILOT_TWITCH_ACCESS_TOKEN", "from-env-token")

    config = load_config()

    assert config.channels.twitch.enabled is True
    assert config.channels.twitch.client_id == "from-env"
    assert config.channels.twitch.access_token == "from-env-token"

