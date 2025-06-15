from minecraft.enums import MinecraftState, Side
from minecraft.protocol.packet import register
from minecraft.protocol.packets.v1_12_2_340.proto_340_packet import Proto340Packet
from minecraft.protocol.types import String, Boolean, Integer, UByte


@register
class JoinGamePacket(Proto340Packet):
    id: int = 35
    state: MinecraftState = MinecraftState.play
    side: Side = Side.clientbound

    fields = {"entity_id": Integer, "gamemode": UByte, "dimension": Integer,
              "difficulty": UByte, "max_players": UByte, "level_type": String,
              "reduced_debug_info": Boolean}
