from pathlib import Path

import orjson
from eth_account.signers.local import LocalAccount
from eth_typing import ChecksumAddress
from web3 import AsyncHTTPProvider, AsyncWeb3
from web3.contract import AsyncContract


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
