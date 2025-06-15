from minecraft.enums import MinecraftState, Side
from minecraft.protocol.packet import register
from minecraft.protocol.packets.v1_12_2_340.proto_340_packet import Proto340Packet
from minecraft.protocol.types import String, Bytes, VarInt


@register
class EncryptionRequestPacket(Proto340Packet):
    id: int = 1
    state: MinecraftState = MinecraftState.login
    side: Side = Side.clientbound

    fields = {"server_id": String, "public_key": Bytes, "verify_token": Bytes}


@register
class EncryptionResponsePacket(Proto340Packet):
    id: int = 1
    state: MinecraftState = MinecraftState.login
    side: Side = Side.serverbound

    fields = {"shared_secret": Bytes, "verify_token": Bytes}


@register
class LoginSuccessPacket(Proto340Packet):
    id: int = 2
    state: MinecraftState = MinecraftState.login
    side: Side = Side.clientbound

    fields = {"uuid": String, "username": String}


@register
class SetCompressionPacket(Proto340Packet):
    id: int = 3
    state: MinecraftState = MinecraftState.login
    side: Side = Side.clientbound

    fields = {"threshold": VarInt}
