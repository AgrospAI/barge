import logging
import argparse
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import httpx
import orjson
from eth_account.signers.local import LocalAccount
from eth_typing import ChecksumAddress
from tenacity import retry, retry_if_result, stop_after_attempt, wait_fixed
from web3 import AsyncHTTPProvider, AsyncWeb3
from web3.contract import AsyncContract
from web3.types import TxParams, TxReceipt

from src.config import Settings

logger = logging.getLogger(__name__)


async def get_web3(rpc_url: str) -> AsyncWeb3[AsyncHTTPProvider]:
    return AsyncWeb3(AsyncHTTPProvider(rpc_url))


def get_web3_account(web3: AsyncWeb3, private_key: str) -> LocalAccount:
    return web3.eth.account.from_key(private_key)


def get_contract(
    web3: AsyncWeb3,
    abi_path: Path,
    contract_address: ChecksumAddress,
) -> AsyncContract:
    artifact = orjson.loads(abi_path.read_bytes())
    abi = artifact.get("abi")

    if abi is None:
        raise ValueError(f"Artifact at {abi_path} does not contain an 'abi' key")

    return web3.eth.contract(
        address=contract_address,
        abi=abi,
    )


@dataclass
class MetadataRequestManager:
    web3: AsyncWeb3
    account: LocalAccount
    contract: AsyncContract

    def __post_init__(self) -> None:
        assert self.web3.is_connected(), "Failed to connect to the RPC node"

    @classmethod
    def abi_path(cls, settings: Settings) -> Path:
        return (
            settings.OCEAN_ARTIFACTS_FOLDER
            / "contracts"
            / "utils"
            / "MetadataRequestManager.sol"
            / "MetadataRequestManager.json"
        )

    @classmethod
    def get_query(cls) -> str:
        return """
            query($id: ID!) {
            metadataRequest(id: $id) {
                id
                erc721
                requester
            }
        }
        """

    async def send(
        self,
        tx: TxParams,
    ) -> TxReceipt:
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = await self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        logger.info("Transaction sent! Hash: %s", tx_hash.hex())

        receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt["status"] == 0:
            # Get the original transaction details
            tx_details = await self.web3.eth.get_transaction(tx_hash)

            # Convert AttributeDict to a plain dict to avoid the .copy() error
            # We also need to remove keys that eth.call doesn't accept
            call_params = {
                "to": tx_details["to"],
                "from": tx_details["from"],
                "value": tx_details["value"],
                "data": tx_details["input"],
                "gas": tx_details["gas"],
                "gasPrice": tx_details["gasPrice"],
            }

            try:
                # Re-run the call at the block before the failure
                await self.web3.eth.call(
                    call_params, block_identifier=receipt["blockNumber"] - 1
                )
            except Exception as e:
                logger.exception(e)

        logger.info("Confirmed in block: %s", receipt.blockNumber)
        return receipt

    async def create(
        self,
        erc721: ChecksumAddress,
        did: ChecksumAddress,
        types: List[int],
        data: List[str],
    ) -> TxReceipt:
        assert not any(n < 0 for n in types), "All types must be >= 0"
        assert len(types) == len(data), "Types must be same length of data"

        nonce = await self.web3.eth.get_transaction_count(self.account.address)

        tx = await self.contract.functions.createRequest(
            erc721, did, types, data
        ).build_transaction(
            {
                "from": self.account.address,
                "nonce": nonce,
                "gas": 2000000,
                "gasPrice": self.web3.to_wei("50", "gwei"),
            }
        )

        return await self.send(tx)

    @retry(
        stop=stop_after_attempt(10),
        wait=wait_fixed(1),
        retry=retry_if_result(lambda res: res is None),
        reraise=True,
    )
    async def get(self, subgraph_url: str, request_id: str) -> Dict | None:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                subgraph_url,
                json={"query": self.get_query(), "variables": {"id": request_id}},
            )
            data = response.json()

            if "errors" in data:
                raise ValueError(f"Subgraph Query Error: {data['errors']}")

            result = data.get("data", {}).get("metadataRequest")
            return result


async def create_metadata_request(chain: str):
    settings = Settings()

    web3 = await get_web3(settings.RPC_URL)
    account = get_web3_account(web3, settings.PRIVATE_KEY.get_secret_value())

    contract = get_contract(
        web3,
        MetadataRequestManager.abi_path(settings),
        settings.contract_address(chain, "MetadataRequestManager"),
    )

    crud = MetadataRequestManager(web3, account, contract)
    await crud.create(
        erc721=web3.to_checksum_address("0x0000000000000000000000000000000000000001"),
        did=web3.to_checksum_address("0x0000000000000000000000000000000000000002"),
        types=[1],
        data=["asd"],
    )


@dataclass
class Args:
    chain: str


def read_arguments() -> Args:
    parser = argparse.ArgumentParser(description="Interact with MetadataRequestManager")

    parser.add_argument(
        "--chain",
        type=str,
        required=True,
        help="The Chain Name (e.g., 'development' for Barge)",
    )

    args = parser.parse_args()

    return Args(args.chain)


async def main():
    args = read_arguments()

    await create_metadata_request(args.chain)


if __name__ == "__main__":
    asyncio.run(main())
