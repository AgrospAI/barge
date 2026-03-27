from typing import Literal

from eth_account import Account
from eth_account.signers.local import LocalAccount
from eth_typing import ChecksumAddress
from ocean_lib.example_config import get_config_dict
from ocean_lib.models.dispenser import DispenserArguments
from ocean_lib.ocean.ocean import Ocean
from ocean_lib.ocean.ocean_assets import OceanAssets
from ocean_lib.ocean.util import to_wei
from ocean_lib.structures.file_objects import UrlFile

from src.config import Settings


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

    tx_dict = {"from": account}
    metadata = OceanAssets.default_metadata(name, tx_dict, type=asset_type)
    metadata.update({"tags": ["Barge"]})

    kwargs = {
        "with_compute": True,
        "wait_for_aqua": True,
        "dt_template_index": 2,
        "pricing_schema_args": DispenserArguments(to_wei(1), to_wei(1)),
        "metadata": metadata,
    }

    match asset_type:
        case "algorithm":
            url = "https://raw.githubusercontent.com/oceanprotocol/c2d-examples/main/branin_and_gpr/gpr.py"
            data_nft, datatoken, ddo = ocean.assets.create_algo_asset(
                name, url, tx_dict, **kwargs
            )

        case "dataset":
            url_file = UrlFile(
                url="https://raw.githubusercontent.com/oceanprotocol/c2d-examples/main/branin_and_gpr/branin.arff"
            )
            data_nft, datatoken, ddo = ocean.assets.create_url_asset(
                name, url_file.url, tx_dict, **kwargs
            )

    if ddo is None:
        raise RuntimeError("Asset created on-chain but metadata publication failed")

    print("Just published asset:")
    print(f"  data_nft: symbol={data_nft.symbol()}, address={data_nft.address}")
    print(f"  datatoken: symbol={datatoken.symbol()}, address={datatoken.address}")
    print(f"  did={ddo.did}")

    return data_nft.address


def __main():
    # Create a dataset for testing purposes

    settings = Settings()

    account = Account.from_key(settings.PRIVATE_KEY.get_secret_value())

    create_asset(account, "dataset")


if __name__ == "__main__":
    __main()
