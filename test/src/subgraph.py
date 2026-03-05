from dataclasses import dataclass, field
from typing import Any, Dict

import httpx
from tenacity import retry, retry_if_result, stop_after_attempt, wait_fixed


@dataclass
class Subgraph:
    url: str
    client_options: Dict = field(default_factory=dict)

    _client: httpx.AsyncClient | None = field(init=False)

    async def __aenter__(self):
        self._client = httpx.AsyncClient(**self.client_options)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        assert self._client is not None
        await self._client.aclose()

        return False

    @retry(
        stop=stop_after_attempt(10),
        wait=wait_fixed(2),
        reraise=True,
    )
    async def query(self, request: httpx.Request) -> httpx.Response:
        assert self._client is not None, "Client not initialized"
        return await self._client.send(request)

    @retry(
        stop=stop_after_attempt(10),
        wait=wait_fixed(2),
        retry=retry_if_result(lambda res: any(v is None for v in res.values())),
        reraise=True,
    )
    async def get(self, query: str, variables: Dict[str, Any]) -> Dict:
        request = httpx.Request(
            method="POST",
            url=self.url,
            json={
                "query": query,
                "variables": variables,
            },
        )

        response = await self.query(request)
        data = response.json()

        if "errors" in data:
            raise ValueError(f"Subgraph Query Error: {data['errors']}")

        return data.get("data")
