import asyncio
import logging

import aionw.aiosocket
from aionw import TCPClient
from aionw.aiosocket import TCPStream


class Interceptor(aionw.aiosocket.TCPServer):
    async def _pipe(self, readable: TCPStream, writable: TCPStream) -> None:
        try:
            while True:
                data = await readable.read_any()
                if not data:
                    break
                writable.write(data)
        finally:
            readable.close()
            writable.close()

    async def pipe_bidirectional(self, client: TCPStream, server: TCPStream) -> None:
        pipe1 = asyncio.create_task(self._pipe(client, server))
        pipe2 = asyncio.create_task(self._pipe(server, client))
        await pipe1
        await pipe2

    async def determine_upstream_address(self, connection: TCPStream) -> tuple[str, int]:
        raise NotImplementedError

    async def upstream_connect(self, host: str, port: int) -> TCPClient:
        raise NotImplementedError

    async def on_intercept(self, client: TCPStream, server: TCPClient) -> None:
        await self.pipe_bidirectional(client, server)

    async def on_connect(self, connection: TCPStream):
        logging.info("Intercepted a connection")
        host, port = await self.determine_upstream_address(connection)
        logging.debug("Intercepted connection host: %s, port: %s", host, port)
        async with (await self.upstream_connect(host, port)) as upstream_conn:
            logging.info("Handling intercepted connection")
            await self.on_intercept(connection, upstream_conn)
