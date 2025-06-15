import logging

import Crypto.Cipher.AES

import utils.logging
from aionw.aiosocket import TCPStream


class OptionalCFBStream(TCPStream):
    def __init__(self, reader=None, writer=None):
        super().__init__(reader=reader, writer=writer)
        self.encryption_enabled: bool = False
        self.encryptor = None
        self.decryptor = None

    def enable_encryption(self, key: bytes) -> None:
        self.encryption_enabled = True
        self.encryptor = Crypto.Cipher.AES.new(key, Crypto.Cipher.AES.MODE_CFB, iv=key)
        self.decryptor = Crypto.Cipher.AES.new(key, Crypto.Cipher.AES.MODE_CFB, iv=key)
        logging.info("Enabled encryption. Key=%s", utils.logging.sensitive(key))

    def write(self, message: bytes) -> None:
        if self.encryption_enabled:
            message = self.encryptor.encrypt(message)
        super().write(message)

    async def read(self, count: int) -> bytes:
        message = await super().read(count)
        if self.encryption_enabled:
            message = self.decryptor.decrypt(message)
        return message
