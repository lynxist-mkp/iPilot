

from abc import ABC, abstractmethod


class BaseChannel(ABC):
    def __init__(self, config, bus):
        self.config = config
        self.bus = bus
    
    @abstractmethod
    async def start(self):
        ...
    
    @abstractmethod
    async def stop(self):
        ...
        