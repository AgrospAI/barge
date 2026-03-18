import json
import logging
from pathlib import Path

import pytest
from web3 import Web3

from src.config import Settings
from src.manager import Manager
from src.queries import get_metadata_request_from_id
from src.subgraph import Subgraph

logger = logging.getLogger(__name__)

zero_address = "0x0000000000000000000000000000000000000000"


@pytest.fixture(scope="session")
async def dataset_algorithm_address(settings: Settings):
    from eth_account import Account

    from src.ocean import create_asset

    store_path = Path(".addresses.json")

    if not store_path.exists():
        account = Account.from_key(settings.PRIVATE_KEY.get_secret_value())
        dataset_address, algorithm_address = (
            create_asset(account, asset_type="dataset"),
            create_asset(account, asset_type="algorithm"),
        )

        store_path.write_text(
            json.dumps(
                {
                    "dataset_address": str(dataset_address),
                    "algorithm_address": str(algorithm_address),
                }
            )
        )

    else:
        stored = json.loads(store_path.read_text())
        dataset_address, algorithm_address = (
            Web3.to_checksum_address(stored["dataset_address"]),
            Web3.to_checksum_address(stored["algorithm_address"]),
        )

    yield dataset_address, algorithm_address


@pytest.mark.asyncio
async def test_nft_created(dataset_algorithm_address):
    logging.info("NFT Address %s", dataset_algorithm_address)
    assert dataset_algorithm_address


def test_get_asset():
    from src.ocean import search_assets

    assets = search_assets()

    print(assets)


@pytest.mark.asyncio
async def test_create_and_verify_subgraph(
    settings: Settings, dataset_algorithm_address
):
    dataset_address, algorithm_address = dataset_algorithm_address

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
        dataset_address,
        algorithm_address,
        [1 & 0xFF],
        ["test"],
        "I want this!",
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
