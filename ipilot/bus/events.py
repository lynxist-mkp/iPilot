from dataclasses import dataclass, field

@dataclass
class InboundMessage:
    channel: str
    chat_id: str
    sender_id: str
    content: str
    metadata: dict = field(default_factory=dict)

    @property
    def session_key(self) -> str:
        return f"{self.channel}:{self.chat_id}"

@dataclass
class OutboundMessage:
    channel: str
    chat_id: str
    content: str
    metadata: dict = field(default_factory=dict)