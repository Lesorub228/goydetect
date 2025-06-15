from typing import Any

from event_base.event_base import EventBase


class ClientBase(EventBase):
    async def _write(self, packet) -> None:
        raise NotImplementedError

    async def write(self, packet) -> None:
        await self._write(packet)
        self._notify_listeners(packet.id, packet)

    async def _read(self, src: Any) -> Any:
        raise NotImplementedError

    async def read(self, src: Any) -> None:
        packet = await self._read(src)
        self._notify_listeners(packet.id, packet)
