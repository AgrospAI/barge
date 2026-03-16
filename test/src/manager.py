from web3.exceptions import ContractLogicError
import logging
from dataclasses import dataclass
from pathlib import Path

from eth_account.signers.local import LocalAccount
from eth_typing import ChecksumAddress
from web3 import AsyncWeb3
from web3.contract import AsyncContract
from web3.types import TxParams, TxReceipt

from src.utils import get_contract, get_web3, get_web3_account

logger = logging.getLogger(__name__)


@dataclass
class Manager:
    web3: AsyncWeb3
    account: LocalAccount
    contract: AsyncContract

    async def check_connected(self) -> None:
        assert await self.web3.is_connected(), "Failed to connect to the RPC node"

    @staticmethod
    async def create(
        rpc_url: str,
        private_key: str,
        artifacts_folder: Path,
        contract_name: str,
        contract_address: ChecksumAddress,
    ) -> "Manager":

        logger.info("Deploying %s from address %s", contract_name, contract_address)

        web3 = await get_web3(
            rpc_url,
        )

        account = get_web3_account(
            web3,
            private_key,
        )

        abi_path = Manager.abi_path(artifacts_folder, contract_name)
        logger.info("ABI Path for %s: %s", contract_name, abi_path)

        contract = get_contract(
            web3,
            abi_path,
            contract_address,
        )

        return Manager(web3, account, contract)

    @classmethod
    def abi_path(cls, base_path: Path, contract_name: str) -> Path:
        pattern = f"*/{contract_name}.json"
        matches = list(base_path.rglob(pattern))

        if not matches:
            raise FileNotFoundError(f"Artifact for {contract_name} not found")

        if len(matches) > 1:
            raise RuntimeError(f"Multiple artifacts found, {contract_name}: {matches}")

        return matches[0]

    async def send_transaction(self, tx: TxParams) -> TxReceipt:
        await self.check_connected()

        # 1. Sign and Send
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = await self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        logger.info("Transaction sent! Hash: %s", tx_hash.hex())

        # 2. Wait for Receipt
        receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash)

        # 3. Handle Failure (Status 0)
        if receipt["status"] == 0:
            logger.error("Transaction failed! Attempting to extract revert reason...")

            # Build params for eth_call to simulate the failure
            # We use 'input' from the transaction as 'data' for the call
            tx_details = await self.web3.eth.get_transaction(tx_hash)

            call_params = {
                "to": tx_details["to"],
                "from": tx_details["from"],
                "value": tx_details["value"],
                "data": tx_details["input"],
            }

            try:
                # We call at the block it failed.
                # Note: Some nodes require 'latest' or 'pending' if
                # the state has moved on, but usually receipt block works.
                await self.web3.eth.call(
                    call_params, block_identifier=receipt["blockNumber"]
                )
            except Exception as e:
                # This 'e' will now contain the actual ContractLogicError
                # (e.g., 'Ownable: caller is not the owner')
                logger.error(f"Revert reason found: {e}")
                # Raising here ensures your pytest actually fails with a useful message
                raise e

        logger.info("Transaction successful in block: %s", receipt["blockNumber"])
        return receipt

    async def call(
        self,
        function: str,
        *args,
    ) -> TxReceipt:
        await self.check_connected()
        try:
            contract_function = getattr(self.contract.functions, function)(*args)

            nonce = await self.web3.eth.get_transaction_count(self.account.address)

            tx = await contract_function.build_transaction(
                {
                    "from": self.account.address,
                    "nonce": nonce,
                    "gas": 2_000_000,
                    "gasPrice": self.web3.to_wei("50", "gwei"),
                }
            )

            receipt = await self.send_transaction(tx)
            return receipt

        except ContractLogicError as e:
            # Catch EVM revert and log the reason
            logger.error(f"Contract reverted during {function} call with args={args}")
            logger.error(f"Revert reason: {e}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error during {function} call with args={args}")
            logger.exception(e)
            raise
