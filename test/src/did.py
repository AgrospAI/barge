import hashlib

from eth_utils import remove_0x_prefix
from eth_utils.address import to_checksum_address
from web3 import Web3


def make_did(chain_id, nft_address):
    return "did:op:" + remove_0x_prefix(
        Web3.to_hex(
            hashlib.sha256(
                (to_checksum_address(nft_address) + str(chain_id)).encode("utf-8")
            ).digest()
        )
    )


chain_id = 8996
nft_address = "0x64EB5fCF130b53e36C84b241a10FFBc9229BB92d"

did = make_did(chain_id, nft_address)

print(did)
