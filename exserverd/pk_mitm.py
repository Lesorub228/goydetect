import logging
import os
from hashlib import sha1
from typing import Optional

from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA

from exserverd.join_interceptor import JoinInterceptor
from exserverd.minecraft_mitm_client import MinecraftMITMClient
from minecraft.networking.minecraft_stream import MinecraftStream
from minecraft.protocol.packets.v1_12_2_340 import EncryptionRequestPacket, EncryptionResponsePacket


class PKMitm(MinecraftMITMClient):
    private_key = RSA.generate(1024)  # A static key, technically makes the MITM detectable, but I don't care
    public_key = private_key.public_key()
    public_key_der = public_key.export_key("DER")

    def __init__(self, cli_to_mitm: MinecraftStream, mitm_to_srv: MinecraftStream, join_interceptor: JoinInterceptor):
        super().__init__(cli_to_mitm, mitm_to_srv)
        self.join_interceptor = join_interceptor
        self._cli_to_mitm_key: Optional[bytes] = None
        self._mitm_to_srv_key: Optional[bytes] = None
        self._shared_secret_replacement: Optional[bytes] = None
        self._verify_token_replacement: Optional[bytes] = None

    def _setup_listeners(self) -> None:
        super()._setup_listeners()
        self.add_pre_listener(EncryptionRequestPacket, self._on_encryption_request)
        self.add_pre_listener(EncryptionResponsePacket, self._pre_encryption_response)
        self.add_post_listener(EncryptionResponsePacket, self._post_encryption_response)

    def _on_encryption_request(self, packet: EncryptionRequestPacket) -> None:
        server_pk: bytes = packet.data["public_key"]
        pkcs_cryptor = PKCS1_v1_5.new(RSA.import_key(server_pk))
        self._mitm_to_srv_key = os.urandom(16)
        self._shared_secret_replacement = pkcs_cryptor.encrypt(self._mitm_to_srv_key)
        self._verify_token_replacement = pkcs_cryptor.encrypt(packet.data["verify_token"])

        sha_hash = sha1()
        sha_hash.update(packet.data["server_id"].encode())
        sha_hash.update(self._mitm_to_srv_key)
        sha_hash.update(server_pk)
        digest = format(int.from_bytes(sha_hash.digest(), 'big', signed=True), 'x')
        self.join_interceptor.set_hash(digest)

        packet.data["public_key"] = self.public_key_der

    def _pre_encryption_response(self, packet: EncryptionResponsePacket) -> None:
        self._cli_to_mitm_key = PKCS1_v1_5.new(self.private_key).decrypt(packet.data["shared_secret"], sentinel=None)
        logging.info("Decrypted the client key: %s", self._cli_to_mitm_key)

        packet.data["shared_secret"] = self._shared_secret_replacement
        packet.data["verify_token"] = self._verify_token_replacement

    def _post_encryption_response(self, packet: EncryptionResponsePacket) -> None:
        self.cli_to_mitm.enable_encryption(self._cli_to_mitm_key)
        self.mitm_to_srv.enable_encryption(self._mitm_to_srv_key)
