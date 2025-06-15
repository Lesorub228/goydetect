import struct
from typing import Optional, Self, BinaryIO, ClassVar
from uuid import UUID

from aionw.aiosocket import TCPStream

SyncWritable = BinaryIO | TCPStream
SyncReadable = BinaryIO


class Serializable:
    @classmethod
    def write(cls, buf: SyncWritable, value) -> None:
        raise NotImplementedError

    @classmethod
    def read(cls, buf: SyncReadable):
        raise NotImplementedError


# dataclasses :sob:
class CompositeStruct(Serializable):
    fields: dict[str, type[Serializable]] = {}

    def __init__(self, data: dict):
        self.data: dict = data

    @classmethod
    def write(cls, buf: SyncWritable, value: Self) -> None:
        for field_name, field_type in cls.fields.items():
            field_type.write(buf, value.data[field_name])

    @classmethod
    def read(cls, buf: SyncReadable) -> Self:
        data = {}
        for field_name, field_type in cls.fields.items():
            data[field_name] = field_type.read(buf)
        return cls(data)

    def __str__(self):
        return f'{self.__class__.__name__}({self.data})'


class SerializableUUID(Serializable):
    @classmethod
    def write(cls, buf: SyncWritable, value: UUID) -> None:
        buf.write(value.bytes)

    @classmethod
    def read(cls, buf: SyncReadable) -> UUID:
        return UUID(bytes=buf.read(16))


class VarInt(Serializable):
    max_bits = 32

    @classmethod
    def write(cls, buf: SyncWritable, value: int) -> None:
        if value >= 2 ** (cls.max_bits - 1) or value < -(2 ** (cls.max_bits - 1)):
            raise RuntimeError("VarInt absolute value is too big")
        value %= 2 ** cls.max_bits
        while True:
            if value < 0b10000000:
                UByte.write(buf, value)
                break
            UByte.write(buf, (value & 0b01111111) | 0b10000000)
            value >>= 7

    @classmethod
    def read(cls, buf: SyncReadable) -> int:
        value = 0
        position = 0
        while True:
            current_byte = buf.read(1)[0]
            value |= (current_byte & 0b01111111) << position
            if (current_byte & 0b10000000) == 0:
                break
            position += 7
            if position >= cls.max_bits:
                raise RuntimeError(f"VarInt absolute value is too big")
        if value & (1 << (cls.max_bits - 1)):
            value -= (1 << cls.max_bits)
        return value


class VarLong(VarInt):
    max_bits = 64


class TrailingBytes(Serializable):
    @classmethod
    def write(cls, buf: SyncWritable, value: bytes) -> None:
        buf.write(value)

    @classmethod
    def read(cls, buf: SyncReadable) -> bytes:
        return buf.read()


class Bytes(Serializable):
    @classmethod
    def write(cls, buf: SyncWritable, value: bytes) -> None:
        VarInt.write(buf, len(value))
        buf.write(value)

    @classmethod
    def read(cls, buf: SyncReadable) -> bytes:
        length = VarInt.read(buf)
        return buf.read(length)


class String(Serializable):
    @classmethod
    def write(cls, buf: SyncWritable, value: str) -> None:
        VarInt.write(buf, len(value))
        buf.write(value.encode("utf-8"))

    @classmethod
    def read(cls, buf: SyncReadable) -> str:
        length = VarInt.read(buf)
        return buf.read(length).decode("utf-8")


class Array(Serializable):
    prefix_type: ClassVar[type[Serializable]]
    element_type: ClassVar[type[Serializable]]

    @classmethod
    def write(cls, buf: SyncWritable, value: list) -> None:
        cls.prefix_type.write(buf, len(value))
        for el in value:
            cls.element_type.write(buf, el)

    @classmethod
    def read(cls, buf: SyncReadable) -> list:
        length = cls.prefix_type.read(buf)
        return [cls.element_type.read(buf) for _ in range(length)]


class Option(Serializable):
    @classmethod
    def write_some(cls, buf: SyncWritable, value) -> None:
        raise NotImplementedError

    @classmethod
    def read_some(cls, buf: SyncReadable):
        raise NotImplementedError

    @classmethod
    def write(cls, buf: SyncWritable, value: Optional) -> None:
        if value is None:
            Boolean.write(buf, False)
            return
        Boolean.write(buf, True)
        cls.write_some(buf, value)

    @classmethod
    def read(cls, buf: SyncReadable) -> Optional:
        if not Boolean.read(buf):
            return
        return cls.read_some(buf)


def _array_type(prefix: type[Serializable], element: type[Serializable]) -> type[Array]:
    class ArrayType(Array):
        prefix_type: ClassVar[type[Serializable]] = prefix
        element_type: ClassVar[type[Serializable]] = element

    return ArrayType


def _optional_type(serializable: type[Serializable]) -> type[Option]:
    class OptionalType(Option):
        @classmethod
        def write_some(cls, buf: SyncWritable, value) -> None:
            serializable.write(buf, value)

        @classmethod
        def read_some(cls, buf: SyncReadable):
            return serializable.read(buf)

    return OptionalType


def _single_struct_type(fmt: str, size: int) -> type[Serializable]:
    class SingleStructType(Serializable):
        @classmethod
        def write(cls, buf: SyncWritable, value) -> None:
            buf.write(struct.pack(fmt, value))

        @classmethod
        def read(cls, buf: SyncReadable):
            return struct.unpack(fmt, buf.read(size))[0]

    return SingleStructType


Boolean = _single_struct_type("?", 1)
Byte = _single_struct_type(">b", 1)
UByte = _single_struct_type(">B", 1)
Short = _single_struct_type(">h", 2)
UShort = _single_struct_type(">H", 2)
Integer = _single_struct_type(">i", 4)
UInteger = _single_struct_type(">I", 4)
Long = _single_struct_type(">q", 8)
ULong = _single_struct_type(">Q", 8)

OptionalULong = _optional_type(ULong)
StringArray = _array_type(VarInt, String)


async def async_read_var_int(buf: TCPStream) -> int:
    value = 0
    position = 0
    while True:
        current_byte = (await buf.read(1))[0]
        value |= (current_byte & 0b01111111) << position
        if (current_byte & 0b10000000) == 0:
            break
        position += 7
        if position >= VarInt.max_bits:
            raise RuntimeError(f"Variable length integer absolute value is too big")
    if value & (1 << (VarInt.max_bits - 1)):
        value -= (1 << VarInt.max_bits)
    return value
