from minecraft.enums import MinecraftState, Side
from minecraft.protocol.packet import register
from minecraft.protocol.packets.v1_12_2_340.proto_340_packet import Proto340Packet
from minecraft.protocol.types import VarInt, String, UShort


@register
class HandshakePacket(Proto340Packet):
    id: int = 0
    state: MinecraftState = MinecraftState.handshaking
    side: Side = Side.serverbound

    fields = {"protocol_version": VarInt, "server_address": String, "server_port": UShort, "next_state": VarInt}
