from typing import TypeVar

from minecraft.enums import MinecraftState, Side, ProtocolVersion
from minecraft.protocol.types import CompositeStruct

PacketFQID = tuple[Side, MinecraftState, int]


class Packet(CompositeStruct):
    # I didn't here use ClassVar bc for unknown packets these are not static
    id: int
    state: MinecraftState
    side: Side
    protocol: ProtocolVersion

    def __init__(self, data: dict):
        super().__init__(data)
        self.event_data: dict = {}

    @classmethod
    def fq_id(cls) -> PacketFQID:
        return cls.side, cls.state, cls.id


PacketType = TypeVar("PacketType", bound=Packet)
PacketTable = dict[PacketFQID, type[PacketType]]

packets: dict[ProtocolVersion, PacketTable] = {}


# idk i don't like __init_subclass__
def register(cls: type[PacketType]):
    if cls.protocol not in packets:
        packets[cls.protocol] = {}
    if cls.fq_id() in packets[cls.protocol]:
        raise ValueError("Packet id collision")
    packets[cls.protocol][cls.fq_id()] = cls
    return cls
