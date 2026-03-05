import argparse
from dataclasses import dataclass

import anyio
from web3 import Web3

from manager import Manager
from src.config import Settings


async def create_metadata_request(chain: str):
    settings = Settings()

    contract_name = "MetadataRequestManager"

    manager = await Manager.create(
        settings.RPC_URL,
        settings.PRIVATE_KEY.get_secret_value(),
        settings.OCEAN_ARTIFACTS_FOLDER,
        contract_name,
        settings.contract_address(chain, "MetadataRequestManager"),
    )

    await manager.call(
        "createRequest",
        Web3.to_checksum_address("0x0000000000000000000000000000000000000001"),
        Web3.to_checksum_address("0x0000000000000000000000000000000000000002"),
        [1],
        ["asd"],
    )


@dataclass
class Args:
    chain: str


def read_arguments() -> Args:
    parser = argparse.ArgumentParser(description="Interact with Contract Manager")

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
    anyio.run(main)
