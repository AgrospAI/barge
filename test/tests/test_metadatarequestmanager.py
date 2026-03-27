import json
import logging
from pathlib import Path

import pytest
import pytest_asyncio
from eth_account import Account
from eth_typing import ChecksumAddress
from src.config import Settings
from src.manager import Manager
from src.ocean import create_asset, search_assets
from src.queries import get_metadata_request_from_id
from src.subgraph import Subgraph
from web3 import Web3

logger = logging.getLogger(__name__)


@pytest_asyncio.fixture(scope="function")
async def create_metadata_request_manager(settings):
    async def create_manager(private_key: str) -> Manager:
        return await Manager.create(
            settings.RPC_URL,
            private_key,
            settings.OCEAN_ARTIFACTS_FOLDER,
            "MetadataRequestManager",
            settings.contract_address("development", "MetadataRequestManager"),
        )

    return create_manager


@pytest_asyncio.fixture(scope="function")
async def metadata_request_manager(settings: Settings, create_metadata_request_manager):
    return await create_metadata_request_manager(
        settings.PRIVATE_KEY.get_secret_value()
    )


@pytest_asyncio.fixture(scope="function")
async def dataset_algorithm_address(
    metadata_request_manager: Manager,
    settings: Settings,
):
    store_path = Path(".addresses.json")

    if store_path.exists():
        stored = json.loads(store_path.read_text())
        dataset_address, algorithm_address = (
            Web3.to_checksum_address(stored["dataset_address"]),
            Web3.to_checksum_address(stored["algorithm_address"]),
        )

        # Check if they exist
        async def address_exists(address: ChecksumAddress) -> bool:
            code = await metadata_request_manager.web3.eth.get_code(address)
            return code not in (b"", b"\x00")

        if await address_exists(dataset_address) and await address_exists(
            algorithm_address
        ):
            return dataset_address, algorithm_address

        logger.info("Current asset addresses not found, creating new")

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

    return dataset_address, algorithm_address


@pytest.mark.asyncio
async def test_nft_created(dataset_algorithm_address):
    logging.info("NFT Address %s", dataset_algorithm_address)
    assert dataset_algorithm_address


@pytest.mark.asyncio
async def test_voting_weight_oracle_set(metadata_request_manager: Manager):
    response = (
        await metadata_request_manager.contract.functions.votingWeightOracle().call()
    )

    checksum_response = Web3.to_checksum_address(response)
    checksum_zeros = Web3.to_checksum_address(
        "0x0000000000000000000000000000000000000000"
    )

    assert checksum_response != checksum_zeros


def test_get_asset():
    assets = search_assets()

    print(assets)


@pytest.mark.asyncio
async def test_create_request_and_verify_subgraph(
    settings: Settings,
    create_metadata_request_manager,
    dataset_algorithm_address,
):
    metadata_request_manager = await create_metadata_request_manager(
        settings.PRIVATE_KEY_2.get_secret_value()
    )

    dataset_address, algorithm_address = dataset_algorithm_address

    # 2. Trigger the Request
    receipt = await metadata_request_manager.call(
        "createRequest",
        {
            "datasetAddress": dataset_address,
            "algorithmAddress": algorithm_address,
            "requestTypes": [1 & 0xFF],
            "data": ["test"],
            "reason": "I want this!",
            "expiresIn": 60,  # in secs
        },
    )

    assert receipt["status"] == 1, "Blockchain transaction failed"

    # 3. Extract ID from logs
    logs = metadata_request_manager.contract.events.RequestCreated().process_receipt(
        receipt
    )
    logger.info("Logs %s", logs)

    request_id = str(logs[0]["args"]["id"])

    async with Subgraph(settings.SUBGRAPH_URL) as subgraph:
        response = await subgraph.get(
            get_metadata_request_from_id(), {"id": request_id}
        )

        logger.info("Subgraph response %s", response)

        assert response
