import asyncio


class ChannelManager:
    def __init__(self):
        self._channels = {}

    def register(self, name: str, channel):
        self._channels[name] = channel

    async def start_all(self):
        if not self._channels:
            return

        tasks = [
            asyncio.create_task(channel.start(), name=f"channel:{name}")
            for name, channel in self._channels.items()
        ]
        await asyncio.gather(*tasks)

    async def stop_all(self):
        if not self._channels:
            return

        await asyncio.gather(*(channel.stop() for channel in self._channels.values()))
