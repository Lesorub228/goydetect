from minecraft.enums import MinecraftState, Side
from minecraft.protocol.packet import register
from minecraft.protocol.packets.v1_12_2_340.proto_340_packet import Proto340Packet
from minecraft.protocol.types import String, Boolean, OptionalULong, StringArray


@register
class TabCompleteRequest(Proto340Packet):
    id: int = 1
    state: MinecraftState = MinecraftState.play
    side: Side = Side.serverbound

    fields = {"text": String, "assume_command": Boolean, "optional_position": OptionalULong}


@register
class TabCompleteResponse(Proto340Packet):
    id: int = 14
    state: MinecraftState = MinecraftState.play
    side: Side = Side.clientbound

    fields = {"matches": StringArray}
