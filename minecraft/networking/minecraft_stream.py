import io
import logging
import zlib
from io import BytesIO
from typing import Optional

import utils.logging
from minecraft.enums import Side, MinecraftState, ProtocolVersion
from minecraft.networking.optional_cfb_stream import OptionalCFBStream
from minecraft.protocol.packet import PacketFQID, Packet, PacketTable, PacketType
from minecraft.protocol.types import async_read_var_int, TrailingBytes, VarInt


class UnknownPacket(Packet):
    fields = {"data": TrailingBytes}

    def fq_id(self) -> PacketFQID:
        return self.side, self.state, self.id


class MinecraftStream(OptionalCFBStream):
    def __init__(self, packets: dict[ProtocolVersion, PacketTable], side: Side, protocol: ProtocolVersion,
                 reader=None, writer=None):
        super().__init__(reader=reader, writer=writer)
        self.packets: dict[PacketFQID, type[PacketType]] = packets[protocol]
        self.side: Side = side
        self.protocol: ProtocolVersion = protocol
        self.compression_enabled: bool = False
        self.compression_threshold: Optional[int] = None
        self.state: MinecraftState = MinecraftState.handshaking

    def enable_compression(self, threshold: int) -> None:
        if threshold < 0:
            return
        logging.info("Enabled compression, threshold=%s", threshold)
        self.compression_enabled = True
        self.compression_threshold = threshold

    def packet_from_data(self, packet_id: int, packet_data: BytesIO) -> PacketType:
        try:
            packet_class = self.packets[(self.side, self.state, packet_id)]
            return packet_class.read(packet_data)
        except KeyError:
            packet = UnknownPacket.read(packet_data)
            packet.id = packet_id
            packet.state = self.state
            packet.side = self.side
            packet.protocol = self.protocol
            return packet

    async def read_packet(self) -> PacketType:
        if not self.compression_enabled:
            length = await async_read_var_int(self)
            packet_data = io.BytesIO(await self.read(length))
            packet_id = VarInt.read(packet_data)
            packet = self.packet_from_data(packet_id, packet_data)
            logging.debug("Read a packet (%s, %s, %s): %s", packet.side, packet.state, packet.id,
                          utils.logging.short(packet))
            return packet

        # may be optimized
        packet_length = await async_read_var_int(self)
        packet_data = io.BytesIO(await self.read(packet_length))
        data_length = VarInt.read(packet_data)
        packet_data = packet_data.read()
        if data_length != 0:
            packet_data = zlib.decompress(packet_data)
        packet_data = io.BytesIO(packet_data)
        packet_id = VarInt.read(packet_data)
        packet = self.packet_from_data(packet_id, packet_data)
        logging.debug("Read a packet (%s, %s, %s): %s", packet.side, packet.state, packet.id,
                      utils.logging.short(packet))
        return packet

    @staticmethod
    def packet_to_bytes(packet: PacketType) -> bytes:
        # write(packet.id); write(packet.content) is more efficient than calling this method
        packet_bytes = io.BytesIO()
        VarInt.write(packet_bytes, packet.id)
        packet.write(packet_bytes, packet)
        packet_bytes.seek(0)
        return packet_bytes.read()

    def write_packet(self, packet: PacketType) -> None:
        logging.debug("Writing a packet (%s, %s, %s): %s", packet.side, packet.state, packet.id,
                      utils.logging.short(packet))
        packet_bytes = self.packet_to_bytes(packet)
        if not self.compression_enabled:
            VarInt.write(self, len(packet_bytes))
            self.write(packet_bytes)
            return
        data_length = 0
        if len(packet_bytes) >= self.compression_threshold:
            data_length = len(packet_bytes)
            packet_bytes = zlib.compress(packet_bytes)
        data_length_bytes_io = io.BytesIO()
        VarInt.write(data_length_bytes_io, data_length)
        data_length_bytes_io.seek(0)
        data_length_bytes = data_length_bytes_io.read()
        VarInt.write(self, len(data_length_bytes) + len(packet_bytes))
        self.write(data_length_bytes)
        self.write(packet_bytes)
