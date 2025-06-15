import logging



import yarl
from aiohttp import ContentTypeError

import aionw.http_client
import utils.logging


class WebhookError(Exception):
    pass


class Webhook(aionw.http_client.HTTPClient):
    def __init__(self, webhook_id: int, webhook_token: str):
        super().__init__(base_url="https://discord.com", headers=None, proxy=None)
        self.webhook_id: int = webhook_id
        self.webhook_token: str = webhook_token
        logging.debug("Initialized a Webhook object with id=%s, token=%s", self.webhook_id,
                      utils.logging.sensitive(self.webhook_token))

    async def execute(self, message: str) -> None:
        path = yarl.URL("/api/webhooks/") / str(self.webhook_id) / self.webhook_token
        logging.debug("Executing a Webhook with id=%s, token=%s", self.webhook_id,
                      utils.logging.sensitive(self.webhook_token))
        async with await self.post(path, json={"content": message}) as response:
            if not response.ok:
                try:
                    response_json = await response.json()
                    error_message = response_json.get("message")
                    if error_message is None:
                        # Probably it's a formatted message with [0] being a template
                        error_message = response_json["content"][0]
                except (ContentTypeError, KeyError):
                    error_message = "Unknown error"
                logging.error("Error while executing a Webhook with id=%s, token=%s: %s (%s)", self.webhook_id,
                              utils.logging.sensitive(self.webhook_token), error_message, response.status)
                raise WebhookError(f'{error_message} ({response.status})')
            logging.debug("Successfully executed a Webhook with id=%s, token=%s", self.webhook_id,
                          utils.logging.sensitive(self.webhook_token))
