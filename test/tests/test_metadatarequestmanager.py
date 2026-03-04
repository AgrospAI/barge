import pytest
import httpx
import asyncio
from src.main import MetadataRequestManager, get_web3, get_web3_account, get_contract


@pytest.mark.asyncio
async def test_create_and_verify_subgraph(settings):
    # 1. Initialize logic
    web3 = await get_web3(settings.RPC_URL)
    account = get_web3_account(web3, settings.PRIVATE_KEY.get_secret_value())
    contract_addr = settings.contract_address("development", "MetadataRequestManager")
    contract = get_contract(
        web3,
        MetadataRequestManager.abi_path(settings),
        contract_addr,
    )

    manager = MetadataRequestManager(web3, account, contract)

    # 2. Trigger the Request
    # We use EnterpriseFeeCollector since it's Ownable
    erc721_test = settings.contract_address("development", "EnterpriseFeeCollector")

    receipt = await manager.create(
        erc721=erc721_test,
        did=erc721_test,
        types=[1],
        data=["test-data"],
    )

    assert receipt["status"] == 1, "Blockchain transaction failed"

    # 3. Extract ID from logs
    # Extract using the contract's helper
    logs = contract.events.RequestCreated().process_receipt(receipt)
    request_id = str(logs[0]["args"]["id"])

    await manager.get(settings.SUBGRAPH_URL, request_id)
