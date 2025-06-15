import socket
from enum import Enum, auto
from typing import Optional, Callable, Coroutine, Any

import exserverd.interceptor.interceptor_base
from aionw import TCPClient
from aionw.aiosocket import TCPStream
from aionw.aiosocket.socks5 import NoAcceptableMethodError, RequestError


class InboundMethod(Enum):
    transparent = auto()  # requires "server_host" and "server_host" inbound parameters
    socks5 = auto()


class OutboundMethod(Enum):
    direct = auto()
    socks5 = auto()  # requires "proxy_host" and "proxy_port" outbound parameters


class Interceptor(exserverd.interceptor.interceptor_base.Interceptor):
    def __init__(self, inbound_method: InboundMethod, outbound_method: OutboundMethod,
                 inbound_params: Optional[dict] = None, outbound_params: Optional[dict] = None):
        self.inbound_method: InboundMethod = inbound_method
        self.outbound_method: OutboundMethod = outbound_method
        self.inbound_params: Optional[dict] = inbound_params
        self.outbound_params: Optional[dict] = outbound_params
        self.inbound_table: dict[InboundMethod, Callable[[TCPStream], Coroutine[Any, Any, tuple[str, int]]]] = {
            InboundMethod.transparent: self.transparent_inbound, InboundMethod.socks5: self.basic_socks5_inbound}
        self.outbound_table: dict[OutboundMethod, Callable[[str, int], Coroutine[Any, Any, TCPClient]]] = {
            OutboundMethod.direct: self.direct_outbound, OutboundMethod.socks5: self.socks5_outbound
        }

    async def transparent_inbound(self, connection: TCPStream) -> tuple[str, int]:
        return self.inbound_params["server_host"], self.inbound_params["server_port"]

    async def basic_socks5_inbound(self, connection: TCPStream) -> tuple[str, int]:
        auth = await connection.read(3)
        if auth != b"\x05\x01\x00":
            connection.write(b"\x05\xff")
            raise NoAcceptableMethodError()
        connection.write(b"\x05\x00")
        req_header = await connection.read(3)
        if req_header != b"\x05\x01\x00":
            connection.write(b"\x05\x01\x00\x01\x00\x00\x00\x00\x00\x00")
            raise RequestError()
        addr_type = await connection.read(1)
        if addr_type == b'\x01':
            address = socket.inet_ntoa(await connection.read(4))
        elif addr_type == b'\x03':
            length = int.from_bytes(await connection.read(1), byteorder="big")
            address = (await connection.read(length)).decode()
        # elif addr_type == b'\x04':
        #     address = socket.inet_ntop(socket.AF_INET6, await connection.read(4))
        else:
            connection.write(b"\x05\x01\x00\x01\x00\x00\x00\x00\x00\x00")
            raise RequestError()
        connection.write(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
        return address, int.from_bytes(await connection.read(2), byteorder="big")

    async def direct_outbound(self, host: str, port: int) -> TCPClient:
        return TCPClient(host, port, proxy_host=None, proxy_port=None)

    async def socks5_outbound(self, host: str, port: int) -> TCPClient:
        return TCPClient(host, port, proxy_host=self.outbound_params["proxy_host"],
                         proxy_port=self.outbound_params["proxy_port"])

    async def determine_upstream_address(self, connection: TCPStream) -> tuple[str, int]:
        return await self.inbound_table[self.inbound_method](connection)

    async def upstream_connect(self, host: str, port: int) -> TCPClient:
        return await self.outbound_table[self.outbound_method](host, port)
