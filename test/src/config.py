from pathlib import Path

import orjson
from eth_typing import ChecksumAddress
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from web3 import Web3


class Settings(BaseSettings):
    RPC_URL: str = Field(...)
    SUBGRAPH_URL: str = Field(...)
    OCEAN_ARTIFACTS_FOLDER: Path = Field(...)
    PRIVATE_KEY: SecretStr = Field(...)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def contract_address(self, chain: str, contract: str) -> ChecksumAddress:
        addresses = orjson.loads(self.address_file.read_bytes())
        address = addresses[chain][contract]
        return Web3.to_checksum_address(address)

    @property
    def address_file(self) -> Path:
        return self.OCEAN_ARTIFACTS_FOLDER / "address.json"
