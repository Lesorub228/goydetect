from minecraft.enums import ProtocolVersion
from minecraft.protocol.packet import Packet


class Proto340Packet(Packet):
    protocol: ProtocolVersion = ProtocolVersion.v1_12_2
