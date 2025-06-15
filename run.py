import asyncio
import logging
import queue
import time
import tomllib
import winsound
from asyncio import Event
from queue import Queue
from typing import Optional

import minecraft.protocol.packet
from aionw import TCPClient
from aionw.aiosocket import TCPStream
from hitler.webhook import Webhook
from exserverd.interceptor.interceptor import InboundMethod, OutboundMethod
from exserverd.join_interceptor import JoinInterceptor
from exserverd.minecraft_interceptor import MinecraftInterceptor
from exserverd.pk_mitm import PKMitm
from minecraft.networking.minecraft_stream import MinecraftStream
from minecraft.protocol.packet import Side, ProtocolVersion, PacketTable
from minecraft.protocol.packets.v1_12_2_340 import TabCompleteRequest, TabCompleteResponse, JoinGamePacket

logging.basicConfig(level=logging.INFO)


class TabRequestEvent:
    def __init__(self, request: TabCompleteRequest, drop_response: bool = False):
        self._event = Event()
        self.request: TabCompleteRequest = request
        self.response: Optional[TabCompleteResponse] = None
        self.drop_response: bool = drop_response

    def set(self, tab_response: TabCompleteResponse) -> None:
        if self.drop_response:
            tab_response.event_data["drop"] = True
        self.response = tab_response
        self._event.set()

    async def wait(self) -> TabCompleteResponse:
        await self._event.wait()
        return self.response


class GDetect(PKMitm):
    def __init__(self, cli_to_mitm: MinecraftStream, mitm_to_srv: MinecraftStream, join_interceptor: JoinInterceptor,
                 config: dict, webhook: Optional[Webhook]):
        super().__init__(cli_to_mitm, mitm_to_srv, join_interceptor)
        self._config: dict = config
        self._webhook: Webhook = webhook
        self._username_triggerlist = {el.casefold() for el in self._config["player_event"]["username_triggerlist"]}
        self._discord_config = self._config["discord"]
        self._webhook_config = self._discord_config["webhook"]
        self._tab_queue: Queue[TabRequestEvent] = Queue()
        self._player_set: set[str] = set()

    def _setup_listeners(self) -> None:
        super()._setup_listeners()
        self.add_pre_listener(TabCompleteRequest, self._on_tab_request)
        self.add_pre_listener(TabCompleteResponse, self._on_tab_response)
        self.add_post_listener(JoinGamePacket, self.on_game_join)

    def on_game_join(self, join_game_packet: JoinGamePacket) -> None:
        logging.info("Joined the game: %s", join_game_packet)
        self.create_task(self.tab_request_loop())

    def _on_tab_request(self, packet: TabCompleteRequest) -> None:
        tab_request_event = TabRequestEvent(packet)
        packet.event_data["event"] = tab_request_event
        self._tab_queue.put_nowait(tab_request_event)

    def _on_tab_response(self, packet: TabCompleteResponse) -> None:
        logging.info('Got tab response')
        try:
            tab_request_event = self._tab_queue.get_nowait()
            packet.data["tab_request"] = tab_request_event.request
            tab_request_event.set(packet)
        except queue.Empty:
            logging.critical("Got a tab response packet, but the queue is empty")
            raise

    async def make_tab_request(self, text: str, assume_command: bool = False,
                               optional_position: Optional[int] = None) -> TabCompleteResponse:
        packet = TabCompleteRequest({"text": text, "assume_command": assume_command,
                                     "optional_position": optional_position})
        self.write_to_server(packet)
        event: TabRequestEvent = packet.event_data["event"]
        event.drop_response = True
        return await event.wait()

    async def discord_event(self, joined: set[str], left: set[str]) -> None:
        if not self._discord_config["enabled"]:
            return
        joined = list(joined)
        left = list(left)
        if not self._config["player_event"]["always_trigger"]:
            joined = [el for el in joined if el.casefold() in self._username_triggerlist]
            left = [el for el in left if el.casefold() in self._username_triggerlist]
        if not (joined or left):
            return
        joined.sort()
        left.sort()
        message = "@everyone\n"
        if joined:
            message += f"Player(s) joined: {', '.join(joined)}\n"
        if left:
            message += f"Player(s) left: {', '.join(left)}\n"
        logging.info("Sending a webhook message")
        winsound.PlaySound('porosyachiy-vizg.wav', winsound.SND_FILENAME | winsound.SND_ASYNC)
        await self._webhook.execute(message)

    async def tab_request_loop(self):
        while True:
            next_t = time.time() + 1
            # it's possible to intercept all tab responses with empty text, but it's almost useless
            tab_response = await self.make_tab_request(" ")
            players = set(tab_response.data["matches"])
            joined = players - self._player_set
            left = self._player_set - players
            self._player_set = players
            self.create_task(self.discord_event(joined=joined, left=left))
            await asyncio.sleep(next_t - time.time())


class GMCInterceptor(MinecraftInterceptor):
    mitm_class = GDetect

    def __init__(self, config: dict, packets: dict[ProtocolVersion, PacketTable], join_interceptor: JoinInterceptor,
                 protocol: ProtocolVersion, inbound_method: InboundMethod, outbound_method: OutboundMethod,
                 inbound_params: Optional[dict] = None, outbound_params: Optional[dict] = None,
                 webhook: Optional[Webhook] = None):
        super().__init__(packets, join_interceptor, protocol,
                         inbound_method, outbound_method, inbound_params, outbound_params)
        self.config: dict = config
        self.webhook: Optional[Webhook] = webhook

    async def on_intercept(self, client: TCPStream, server: TCPClient) -> None:
        logging.info("Intercepted a Minecraft connection")
        client_to_interceptor = MinecraftStream(packets=self.packets, side=Side.serverbound, protocol=self.protocol,
                                                reader=client.reader, writer=client.writer)
        interceptor_to_server = MinecraftStream(packets=self.packets, side=Side.clientbound, protocol=self.protocol,
                                                reader=server.reader, writer=server.writer)
        mitm = self.mitm_class(cli_to_mitm=client_to_interceptor, mitm_to_srv=interceptor_to_server,
                               join_interceptor=self.join_interceptor, config=self.config, webhook=self.webhook)
        await mitm.run()


async def main():
    with open('config.toml', 'rb') as file:
        config = tomllib.load(file)
    discord_config = config['discord']
    webhook = Webhook(webhook_id=discord_config['webhook']['id'], webhook_token=discord_config['webhook']['token'])
    async with webhook:
        join_interceptor = JoinInterceptor(inbound_method=InboundMethod.socks5,
                                           outbound_method=OutboundMethod.direct,
                                           inbound_params={"server_host": "ex-server.ru", "server_port": 80},
                                           outbound_params={})
        await join_interceptor.run('127.0.0.1', 1234)
        protocol = ProtocolVersion.v1_12_2
        packets = minecraft.protocol.packet.packets
        minecraft_interceptor = GMCInterceptor(packets=packets, join_interceptor=join_interceptor,
                                               protocol=protocol, inbound_method=InboundMethod.socks5,
                                               outbound_method=OutboundMethod.direct,
                                               config=config, webhook=webhook
                                               )
        await minecraft_interceptor.run('127.0.0.1', 1235)
        await asyncio.Event().wait()


if __name__ == '__main__':
    asyncio.run(main())
