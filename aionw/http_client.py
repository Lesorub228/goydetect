from typing import Optional, Self

import aiohttp
from aiohttp.client import _RequestContextManager, ClientSession
from aiohttp.typedefs import StrOrURL, LooseHeaders


class HTTPClient:
    def __init__(self, base_url: StrOrURL, headers: Optional[LooseHeaders], proxy: Optional[StrOrURL]):
        self._session: Optional[ClientSession] = None
        self._base_url: StrOrURL = base_url
        self._headers: Optional[LooseHeaders] = headers
        self._proxy: Optional[StrOrURL] = proxy

    async def __aenter__(self) -> Self:
        self._session = aiohttp.ClientSession(base_url=self._base_url,
                                              headers=self._headers)
        await self._session.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._session.__aexit__(exc_type, exc_val, exc_tb)
        self._session = None

    def _request(self, method: str, path: StrOrURL, kwargs) -> _RequestContextManager:
        return self._session.request(method, path, proxy=self._proxy, **kwargs)

    def get(self, path: StrOrURL, **kwargs) -> _RequestContextManager:
        return self._request(aiohttp.hdrs.METH_GET, path, kwargs)

    def post(self, path: StrOrURL, **kwargs) -> _RequestContextManager:
        return self._request(aiohttp.hdrs.METH_POST, path, kwargs)
