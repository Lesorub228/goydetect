import logging

from exserverd.minecraft_mitm import MinecraftMITM
from minecraft.enums import MinecraftState
from minecraft.protocol.packets.v1_12_2_340 import HandshakePacket, LoginSuccessPacket, SetCompressionPacket


class MinecraftMITMClient(MinecraftMITM):
    def _setup_listeners(self) -> None:
        super()._setup_listeners()  # in case I add some listeners to the base class
        self.add_post_listener(HandshakePacket, self._post_handshake)
        self.add_post_listener(LoginSuccessPacket, self._post_login_success)
        self.add_post_listener(SetCompressionPacket, self._post_set_compression)

    def _post_handshake(self, packet: HandshakePacket) -> None:
        next_state = MinecraftState(packet.data["next_state"])
        logging.info("Received a handshake. Next state: %s", next_state)
        self.cli_to_mitm.state = next_state
        self.mitm_to_srv.state = next_state

    def _post_login_success(self, packet: LoginSuccessPacket) -> None:
        logging.info("Received a Login Success packet")
        self.cli_to_mitm.state = MinecraftState.play  # 1.21+ protocols have an additional state
        self.mitm_to_srv.state = MinecraftState.play

    def _post_set_compression(self, packet: SetCompressionPacket) -> None:
        threshold = packet.data["threshold"]
        self.cli_to_mitm.enable_compression(threshold)
        self.mitm_to_srv.enable_compression(threshold)
