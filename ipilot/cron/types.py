from dataclasses import dataclass, asdict


@dataclass
class CronJob:
    id: str
    prompt: str
    schedule: str
    next_run_at: str | None = None
    enabled: bool = True

    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)