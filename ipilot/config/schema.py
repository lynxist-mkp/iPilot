from pathlib import Path

from pydantic import BaseModel, Field

class AgentDefaults(BaseModel):
    workspace: str = "~/.ipilot/workspace"
    model: str = "step-3.5-flash"
    provider: str = "stepfun"
    temperature: float = 0.0

class AgentsConfig(BaseModel):
    defaults: AgentDefaults = Field(default_factory=AgentDefaults)

class ProviderConfig(BaseModel):
    api_key: str = ""
    api_base: str | None = None

class ProvidersConfig(BaseModel):
    stepfun: ProviderConfig = Field(default_factory=ProviderConfig)

class ToolsConfig(BaseModel):
    restrict_to_workspace: bool = False


class McpServerConfig(BaseModel):
    name: str
    url: str
    enabled: bool = True
    transport: str = "streamable-http"
    timeout_seconds: float = 30.0


class McpConfig(BaseModel):
    servers: list[McpServerConfig] = Field(default_factory=list)


class TwitchChannelConfig(BaseModel):
    enabled: bool = False
    client_id: str = ""
    access_token: str = ""
    broadcaster_id: str = ""
    sender_id: str = ""
    eventsub_ws_url: str = "wss://eventsub.wss.twitch.tv/ws"
    helix_api_base: str = "https://api.twitch.tv/helix"


class ChannelsConfig(BaseModel):
    twitch: TwitchChannelConfig = Field(default_factory=TwitchChannelConfig)


class Config(BaseModel):
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    mcp: McpConfig = Field(default_factory=McpConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)

    @property
    def workspace_path(self) -> Path:
        return Path(self.agents.defaults.workspace).expanduser()
