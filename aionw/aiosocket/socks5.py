import ipaddress
from typing import Optional

from . import tcp

IPAddrOrDomain = ipaddress.IPv4Address | ipaddress.IPv6Address | str


class Address:
    IPv4 = 0x01
    domain_name = 0x03
    IPv6 = 0x04
    addr_map = {ipaddress.IPv4Address: IPv4, ipaddress.IPv6Address: IPv6,
                str: domain_name}

    def __init__(self, addr: IPAddrOrDomain):
        if type(addr) is str:
            addr = self.string_to_address(addr)
        self._addr: IPAddrOrDomain = addr
        self.type: int = self.addr_map[type(self._addr)]

    def to_bytes(self):
        if self.type == self.domain_name:
            packed_length = len(self._addr).to_bytes(length=1, byteorder='big')
            return packed_length + self._addr.encode()
        return self._addr.packed

    @staticmethod
    def string_to_address(string: str) -> IPAddrOrDomain:
        try:
            string = ipaddress.IPv4Address(string)
        except ipaddress.AddressValueError:
            try:
                string = ipaddress.IPv6Address(string)
            except ipaddress.AddressValueError:  # string is a domain name
                pass
        return string


class AuthMethod:
    no_auth = 0
    no_acceptable_method = 255


class Command:
    connect = 1
    bind = 2
    associate_udp = 3


class SocksServerError(Exception):
    pass


class IncompatibleVersionError(SocksServerError):
    pass


class NoAcceptableMethodError(SocksServerError):
    pass


class RequestError(SocksServerError):
    pass


response_status = {
    0x00: 'Request granted',
    0x01: 'General SOCKS server failure',
    0x02: 'Connection not allowed by the ruleset',
    0x03: 'Network unreachable',
    0x04: 'Host unreachable',
    0x05: 'Connection refused by destination host',
    0x06: 'TTL expired',
    0x07: 'Command not supported',
    0x08: 'Address type not supported',
}

request_granted = 0x00


class Socks5CompatibleStream(tcp.TCPStream):
    version = 5

    def _write_int(self, integer: int, length: int = 1, signed=False):
        self.write(integer.to_bytes(length=length, byteorder='big',
                                    signed=signed))

    async def _read_int(self, length: int = 1, signed=False):
        return int.from_bytes(await self.read(length), byteorder='big',
                              signed=signed)

    def _write_version(self):
        self._write_int(self.version)

    async def _read_version(self):
        srv_ver = await self._read_int()
        if srv_ver != self.version:
            raise IncompatibleVersionError(
                f"Received version ({srv_ver}) does not equal to expected "
                f"version ({self.version})"
            )

    async def _read_addr(self) -> Address:
        addr_type = await self._read_int()
        if addr_type == Address.IPv4:
            address = ipaddress.IPv4Address(await self.read(4))
        elif addr_type == Address.IPv6:
            address = ipaddress.IPv4Address(await self.read(16))
        elif addr_type == Address.domain_name:
            address = (await self.read(await self._read_int())).decode()
        else:
            raise NotImplementedError(f"Unknown address type: {addr_type}")
        return Address(address)

    def _write_addr(self, addr: Address):
        self._write_int(addr.type)
        self.write(addr.to_bytes())


class Socks5Stream(Socks5CompatibleStream):
    def __init__(self, proxy_host: Optional[str], proxy_port: Optional[int], reader=None, writer=None):
        super().__init__(reader=reader, writer=writer)
        self.proxy_host: Optional[str] = proxy_host
        self.proxy_port: Optional[int] = proxy_port

    async def _do_greeting(self, auth_methods=None) -> int:
        if auth_methods is None:
            auth_methods = [AuthMethod.no_auth]
        self._write_version()
        self._write_int(len(auth_methods))
        for method in auth_methods:
            self._write_int(method)
        await self._read_version()
        server_choice = await self._read_int()
        return server_choice

    async def _do_command(self, address: Address, port: int, command: int):
        self._write_version()
        self._write_int(command)
        self._write_int(0)  # Reserved byte
        self._write_addr(address)
        self._write_int(port, length=2)
        await self._read_version()
        status = await self._read_int(1)
        if status != request_granted:
            raise RequestError(response_status[status])
        reserved = await self._read_int()
        if reserved != 0:
            raise IncompatibleVersionError(f"Server set reserved byte to {reserved} "
                                           f"(Unknown SOCKS5 extension)")
        bound_address = await self._read_addr()
        bound_port = await self._read_int(2)
        return bound_address, bound_port

    async def _socks_auth(self, auth_methods=None):
        server_choice = await self._do_greeting(auth_methods=auth_methods)
        if server_choice == AuthMethod.no_acceptable_method:
            raise NoAcceptableMethodError
        if server_choice != AuthMethod.no_auth:
            raise NotImplementedError

    async def _socks_connect(self, host: Address, port: int, auth_methods=None):
        await self._socks_auth(auth_methods)
        await self._do_command(host, port, Command.connect)

    async def connect(self, host: str | Address, port: int):
        if self.proxy_host is None and self.proxy_port is None:
            await super().connect(host, port)
            return
        await super().connect(self.proxy_host, self.proxy_port)
        if type(host) is str:
            host = Address(host)
        await self._socks_connect(host, port)
