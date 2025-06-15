import asyncio
import logging
from enum import Enum, auto
from typing import Callable, Any

from event_base.event_base import EventBase
from minecraft.networking.minecraft_stream import MinecraftStream
from minecraft.protocol.packet import PacketFQID, PacketType
from minecraft.protocol.packets.v1_12_2_340 import EncryptionResponsePacket, LoginSuccessPacket


class ForwardState(Enum):
    pre = auto()
    post = auto()


PacketEvent = tuple[ForwardState, PacketFQID]

# adding | Callable[[], None] breaks the type checker for some reason
PacketEventCallable = Callable[[PacketType], Any]


class MinecraftMITM(EventBase):
    def __init__(self, cli_to_mitm: MinecraftStream, mitm_to_srv: MinecraftStream):
        super().__init__()
        self.cli_to_mitm: MinecraftStream = cli_to_mitm
        self.mitm_to_srv: MinecraftStream = mitm_to_srv

    def add_listener(self, event: PacketEvent, function: PacketEventCallable) -> None:
        super().add_listener(event, function)

    @staticmethod
    def pre_event(packet: type[PacketType] | PacketType) -> PacketEvent:
        return ForwardState.pre, packet.fq_id()

    @staticmethod
    def post_event(packet: type[PacketType] | PacketType) -> PacketEvent:
        return ForwardState.post, packet.fq_id()

    def add_pre_listener(self, packet: type[PacketType], function: PacketEventCallable) -> None:
        self.add_listener(self.pre_event(packet), function)

    def add_post_listener(self, packet: type[PacketType], function: PacketEventCallable) -> None:
        self.add_listener(self.post_event(packet), function)

    def remove_listener(self, event: PacketEvent, function: PacketEventCallable) -> None:
        super().remove_listener(event, function)

    def wait_for(self, event: PacketEvent) -> asyncio.Task:
        return super().wait_for(event)

    def _write(self, stream: MinecraftStream, packet: PacketType) -> None:
        self._notify_listeners(self.pre_event(packet), packet)  # all patchers must be synchronous
        if packet.event_data.get("drop"):
            return
        stream.write_packet(packet)
        self._notify_listeners(self.post_event(packet), packet)

    def write_to_server(self, packet: PacketType) -> None:
        self._write(self.mitm_to_srv, packet)

    def write_to_client(self, packet: PacketType) -> None:
        self._write(self.cli_to_mitm, packet)

    async def recv_loop(self, readable: MinecraftStream, writable: MinecraftStream):
        while True:
            try:
                packet = await readable.read_packet()
                self._write(writable, packet)
                if packet.fq_id() == EncryptionResponsePacket.fq_id():
                    await self.wait_for(self.post_event(LoginSuccessPacket))  # prevents compression race condition
            except asyncio.IncompleteReadError:
                logging.debug("recv_loop: packet read error (connection closed)")
                readable.close()  # both close() calls are useless but anyway
                writable.close()
                break

    async def _close(self) -> None:
        logging.info("Minecraft connection closed")
        self.cli_to_mitm.close()
        self.mitm_to_srv.close()

    async def _run(self):
        loop1 = self.create_task(self.recv_loop(self.cli_to_mitm, self.mitm_to_srv))
        loop2 = self.create_task(self.recv_loop(self.mitm_to_srv, self.cli_to_mitm))
        logging.info("MinecraftMITM is running")
        await loop1
        await loop2  # unnecessary
