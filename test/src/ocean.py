from typing import Literal
from ocean_lib.ocean.ocean_assets import OceanAssets
from eth_account.signers.local import LocalAccount
from eth_typing import ChecksumAddress
from ocean_lib.example_config import get_config_dict
from ocean_lib.ocean.ocean import Ocean


def search_assets(query: str = "test"):
    config = get_config_dict("http://localhost:8545")

    config.update(
        {
            "METADATA_CACHE_URI": "http://localhost:10000",
            "PROVIDER_URL": "http://provider:8030",
        }
    )

    ocean = Ocean(config)

    results = ocean.assets.search(query)

    return results


def create_asset(
    account: LocalAccount,
    asset_type: Literal["algorithm", "dataset"] = "dataset",
) -> tuple[ChecksumAddress, str]:
    """
    Creates an Ocean asset and returns the DataNFT address.
    """

    config = get_config_dict("http://localhost:8545")

    config.update(
        {
            "METADATA_CACHE_URI": "http://localhost:10000",
            "PROVIDER_URL": "http://provider:8030",
        }
    )

    ocean = Ocean(config)

    OCEAN = ocean.OCEAN_token

    assert ocean.wallet_balance(account) > 0, "account needs ETH"
    assert OCEAN.balanceOf(account) > 0, "account needs OCEAN"

    name = f"test script {asset_type}"
    url = "https://raw.githubusercontent.com/trentmc/branin/main/branin.arff"

    tx_dict = {"from": account}
    data_nft, datatoken, ddo = ocean.assets.create_url_asset(
        name,
        url,
        tx_dict,
        with_compute=True,
        metadata=OceanAssets.default_metadata(name, tx_dict, type=asset_type),
    )

    if ddo is None:
        raise RuntimeError("Asset created on-chain but metadata publication failed")

    print("Just published asset:")
    print(f"  data_nft: symbol={data_nft.symbol()}, address={data_nft.address}")
    print(f"  datatoken: symbol={datatoken.symbol()}, address={datatoken.address}")
    print(f"  did={ddo.did}")

    return data_nft.address
