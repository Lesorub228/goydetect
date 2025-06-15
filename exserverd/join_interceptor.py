import json
import logging
from typing import Optional

import utils.logging
from aionw import TCPClient
from aionw.aiosocket import TCPStream
from exserverd.interceptor.interceptor import Interceptor, InboundMethod, OutboundMethod


def json_encode(data: dict) -> bytes:
    return json.dumps(data, separators=(",", ":")).encode()
    # return json.dumps(data).encode()


class JoinInterceptor(Interceptor):
    def __init__(self, inbound_method: InboundMethod, outbound_method: OutboundMethod,
                 inbound_params: Optional[dict] = None, outbound_params: Optional[dict] = None):
        super().__init__(inbound_method, outbound_method, inbound_params, outbound_params)
        self._new_hash: Optional[str] = None

    def set_hash(self, repl_hash: str) -> None:
        self._new_hash = repl_hash

    # This method preserves the client request format, so a modified request is indistinguishable from a real one
    async def on_intercept(self, client: TCPStream, server: TCPClient):
        logging.info("Intercepting a request to ex-server.ru")
        request_line = await client.read_line()
        logging.info("Request line is: %s", request_line)
        if b"/exUUIDAuth.php?action=join" not in request_line:
            logging.info("Not a join request, ignoring")
            server.write(request_line)
            await self.pipe_bidirectional(client, server)
            return
        logging.info("Patching a join request")
        headers = []
        content_length_idx = None
        i = 0
        while True:
            line = await client.read_line()
            if not line.strip():
                headers_end = line
                break
            key, value = line.split(b":")
            headers.append([key, value])
            if key.lower() == b"content-length":
                content_length_idx = i
            i += 1
        if content_length_idx is None:
            raise ValueError("No Content-Length reader found. Is request chunked?")
        content_length = int(headers[content_length_idx][1])
        raw_content = await client.read(content_length)
        content = json.loads(raw_content)
        if json_encode(content) != raw_content:
            logging.error("Interceptor JSON: %s; client JSON: %s",
                          json_encode(content),  raw_content)
            raise ValueError("Interceptor and client have different JSON string representations")
        if not self._new_hash:
            raise ValueError("Replacement hash is not set")
        content["serverId"]: str = self._new_hash
        self._new_hash = None
        raw_content = json_encode(content)
        headers[content_length_idx][1] = headers[content_length_idx][1].replace(str(content_length).encode(),
                                                                                str(len(raw_content)).encode())
        server.write(request_line)
        for key, value in headers:
            server.write(key)
            server.write(b":")
            server.write(value)
        server.write(headers_end)
        server.write(raw_content)
        logging.info("Patched a join request. New serverId=%s", utils.logging.sensitive(content["serverId"]))
        await self.pipe_bidirectional(client, server)
