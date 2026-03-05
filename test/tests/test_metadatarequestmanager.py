import logging
import pytest

from src.config import Settings
from src.manager import Manager
from src.queries import get_metadata_request_from_id
from src.subgraph import Subgraph

logger = logging.getLogger(__name__)

zero_address = "0x0000000000000000000000000000000000000000"


@pytest.fixture
async def nft_address(settings: Settings):
    manager = await Manager.create(
        settings.RPC_URL,
        settings.PRIVATE_KEY.get_secret_value(),
        settings.OCEAN_ARTIFACTS_FOLDER,
        "ERC721Factory",
        settings.contract_address("development", "ERC721Factory"),
    )

    receipt = await manager.call(
        "deployERC721Contract",
        "TestNFT",
        "TNFT",
        1,
        zero_address,
        zero_address,
        "data:application/json;base64,eyJuYW1lIjoiUFggRGF0YSBORlQiLCJzeW1ib2wiOiJQWC1ORlQiLCJkZXNjcmlwdGlvbiI6IkRhdGEgTkZUcyBhcmUgdW5pcXVlIGRpZ2l0YWwgYXNzZXRzIHRoYXQgcmVwcmVzZW50IHRoZSBpbnRlbGxlY3R1YWwgcHJvcGVydHkgb2YgeW91ciBkaWdpdGFsIHNlcnZpY2VzLiIsImV4dGVybmFsX3VybCI6Imh0dHBzOi8vcG9ydGFsLnBvbnR1cy14LmV1L2Fzc2V0L2RpZDpvcDpjMTNkZWJmODFlNzBlZTQyMWE2ODAxZDFiNWM5ZTljNmUyMjRlNmE5ODc0NjNlYjk4YTQ1ZDNkNzc0NDE1OGE2IiwiYmFja2dyb3VuZF9jb2xvciI6IjE0MTQxNCIsImltYWdlX2RhdGEiOiJkYXRhOmltYWdlL3N2Zyt4bWwsJTNDc3ZnIHZpZXdCb3g9JzAgMCA5OSA5OScgZmlsbD0ndW5kZWZpbmVkJyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnJTNFJTNDcGF0aCBmaWxsPSclMjMwMDk3OTNmZicgZD0nTTAsOTlMMCwyOUM5LDI1IDE5LDIyIDI3LDIxQzM0LDE5IDQwLDE4IDQ4LDIxQzU1LDIzIDY1LDI4IDc0LDMxQzgyLDMzIDkwLDMxIDk5LDMwTDk5LDk5WicvJTNFJTNDcGF0aCBmaWxsPSclMjMwMDhiYWFmZicgZD0nTTAsOTlMMCw0M0M2LDQzIDEzLDQzIDIyLDQ1QzMwLDQ2IDQwLDQ5IDQ5LDUxQzU3LDUyIDY1LDUzIDc0LDU0QzgyLDU0IDkwLDU0IDk5LDU0TDk5LDk5WiclM0UlM0MvcGF0aCUzRSUzQ3BhdGggZmlsbD0nJTIzMDA0OTY3ZmYnIGQ9J00wLDk5TDAsNzhDNyw3NCAxNSw3MSAyMyw3MEMzMCw2OSAzNiw3MCA0Niw3MkM1NSw3MyA2Niw3NSA3Niw3NUM4NSw3NSA5Miw3MyA5OSw3Mkw5OSw5OVonJTNFJTNDL3BhdGglM0UlM0Mvc3ZnJTNFIn0=",
        False,
        manager.account.address,
    )

    assert receipt["status"] == 1, "NFT creation transaction failed"

    event_logs = await manager.contract.events.NFTCreated().get_logs(
        argument_filters={},
        from_block=receipt["blockNumber"],
        to_block=receipt["blockNumber"],
    )
    # Ensure the tx hash matches to avoid picking up other people's transactions on a public testnet
    logs = [
        log
        for log in event_logs
        if log["transactionHash"] == receipt["transactionHash"]
    ]
    yield logs[0]["args"]["newTokenAddress"]


@pytest.mark.asyncio
async def test_nft_created(nft_address):
    logging.info("NFT Address %s", nft_address)
    assert nft_address


@pytest.mark.asyncio
async def test_create_and_verify_subgraph(settings: Settings, nft_address):
    manager = await Manager.create(
        settings.RPC_URL,
        settings.PRIVATE_KEY.get_secret_value(),
        settings.OCEAN_ARTIFACTS_FOLDER,
        "MetadataRequestManager",
        settings.contract_address("development", "MetadataRequestManager"),
    )

    # 2. Trigger the Request
    receipt = await manager.call(
        "createRequest",
        nft_address,
        nft_address,
        [1 & 0xFF],
        ["test"],
    )

    assert receipt["status"] == 1, "Blockchain transaction failed"

    # 3. Extract ID from logs
    logs = manager.contract.events.RequestCreated().process_receipt(receipt)
    logger.info("Logs %s", logs)

    request_id = str(logs[0]["args"]["id"])

    async with Subgraph(settings.SUBGRAPH_URL) as subgraph:
        response = await subgraph.get(
            get_metadata_request_from_id(), {"id": request_id}
        )

        logger.info("Subgraph response %s", response)

        assert response
