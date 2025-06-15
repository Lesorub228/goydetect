import asyncio


class TCPStream:
    def __init__(self, reader=None, writer=None):
        self.reader = reader
        self.writer = writer

    async def connect(self, host: str, port: int, ssl_context=None) -> None:
        self.reader, self.writer = await asyncio.open_connection(host, port,
                                                                 ssl=ssl_context)

    @property
    def closed(self) -> bool:
        return self.writer.is_closing()

    def close(self) -> None:
        if self.writer is not None:
            self.writer.close()

    def write(self, data: bytes) -> None:
        self.writer.write(data)

    async def drain(self) -> None:
        await self.writer.drain()

    async def read(self, count: int) -> bytes:
        return await self.reader.readexactly(count)

    async def read_any(self, max_count: int = 4096) -> bytes:
        return await self.reader.read(max_count)

    async def read_until(self, sep: bytes) -> bytes:
        return await self.reader.readuntil(sep)

    async def read_line(self) -> bytes:
        return await self.reader.readline()
