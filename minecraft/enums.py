from enum import Enum, auto


class MinecraftState(Enum):
    handshaking = 0
    status = auto()
    login = auto()
    transfer = auto()
    configuration = auto()
    play = auto()


class Side(Enum):
    clientbound = auto()
    serverbound = auto()


class ProtocolVersion(Enum):
    v1_12_2 = 340
