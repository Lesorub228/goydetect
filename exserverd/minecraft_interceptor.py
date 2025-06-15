import logging
from typing import Optional

from aionw import TCPClient
from aionw.aiosocket import TCPStream
from exserverd.interceptor.interceptor import Interceptor, OutboundMethod, InboundMethod
from exserverd.join_interceptor import JoinInterceptor
from exserverd.pk_mitm import PKMitm
from minecraft.enums import Side, ProtocolVersion
from minecraft.networking.minecraft_stream import MinecraftStream
from minecraft.protocol.packet import PacketTable


class MinecraftInterceptor(Interceptor):
    mitm_class = PKMitm

    def __init__(self, packets: dict[ProtocolVersion, PacketTable], join_interceptor: JoinInterceptor,
                 protocol: ProtocolVersion, inbound_method: InboundMethod, outbound_method: OutboundMethod,
                 inbound_params: Optional[dict] = None, outbound_params: Optional[dict] = None):
        super().__init__(inbound_method, outbound_method, inbound_params, outbound_params)
        self.packets: dict[ProtocolVersion, PacketTable] = packets
        self.join_interceptor: JoinInterceptor = join_interceptor
        self.protocol: ProtocolVersion = protocol

    async def on_intercept(self, client: TCPStream, server: TCPClient) -> None:
        logging.info("Intercepted a Minecraft connection")
        client_to_interceptor = MinecraftStream(packets=self.packets, side=Side.serverbound, protocol=self.protocol,
                                                reader=client.reader, writer=client.writer)
        interceptor_to_server = MinecraftStream(packets=self.packets, side=Side.clientbound, protocol=self.protocol,
                                                reader=server.reader, writer=server.writer)
        mitm = self.mitm_class(cli_to_mitm=client_to_interceptor, mitm_to_srv=interceptor_to_server,
                               join_interceptor=self.join_interceptor)
        await mitm.run()
