from typing import Optional

from . import aiosocket


class TCPClient(aiosocket.Socks5Stream):
    def __init__(self, host: str, port: int, proxy_host: Optional[str], proxy_port: Optional[int]):
        self.host = host
        self.port = port
        super().__init__(proxy_host, proxy_port)

    async def __aenter__(self):
        await self.connect(self.host, self.port)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.writer:
                await self.drain()
        except ConnectionResetError:
            pass
        self.close()
