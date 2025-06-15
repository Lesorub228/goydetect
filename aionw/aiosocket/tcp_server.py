import asyncio
import traceback

from . import tcp

tasks = set()


class TCPServer:
    async def on_connect(self, connection: tcp.TCPStream):
        pass

    async def _on_connect(self, reader, writer):
        try:
            await self.on_connect(tcp.TCPStream(reader=reader, writer=writer))
        except Exception as ex:
            traceback.print_exception(ex)
            raise
        finally:
            writer.close()

    async def i_hate_garbage_collector(self, reader, writer):
        task = asyncio.create_task(self._on_connect(reader, writer))
        tasks.add(task)
        task.add_done_callback(tasks.remove)

    async def run(self, host: str, port: int) -> None:
        await asyncio.start_server(self.i_hate_garbage_collector, host, port)

    async def run_forever(self, host: str, port: int) -> None:
        await self.run(host, port)
        await asyncio.Event().wait()
