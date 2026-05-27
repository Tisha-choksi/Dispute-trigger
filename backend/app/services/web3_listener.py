import asyncio
import json
import logging
from typing import Callable

from web3 import Web3
from web3.types import EventData

logger = logging.getLogger(__name__)


class DisputeEventListener:
    def __init__(
        self,
        rpc_url: str,
        contract_address: str,
        abi: list,
        on_dispute_raised: Callable,
        on_evidence_submitted: Callable,
        on_resolution_proposed: Callable,
        on_dispute_resolved: Callable,
        poll_interval: int = 2,
    ):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.contract = self.w3.eth.contract(address=contract_address, abi=abi)
        self.poll_interval = poll_interval
        self.on_dispute_raised = on_dispute_raised
        self.on_evidence_submitted = on_evidence_submitted
        self.on_resolution_proposed = on_resolution_proposed
        self.on_dispute_resolved = on_dispute_resolved

    async def listen_forever(self):
        last_block = self.w3.eth.block_number

        logger.info(f"Starting event listener from block {last_block}")

        while True:
            try:
                current_block = self.w3.eth.block_number

                if current_block > last_block:
                    await self._process_events(last_block + 1, current_block)
                    last_block = current_block

                await asyncio.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Listener error: {e}")
                await asyncio.sleep(5)

    async def _process_events(self, from_block: int, to_block: int):
        events = self.contract.events.DisputeRaised.get_logs(
            from_block=from_block, to_block=to_block
        )
        for event in events:
            await self.on_dispute_raised(event)

        events = self.contract.events.EvidenceSubmitted.get_logs(
            from_block=from_block, to_block=to_block
        )
        for event in events:
            await self.on_evidence_submitted(event)

        events = self.contract.events.ResolutionProposed.get_logs(
            from_block=from_block, to_block=to_block
        )
        for event in events:
            await self.on_resolution_proposed(event)

        events = self.contract.events.DisputeResolved.get_logs(
            from_block=from_block, to_block=to_block
        )
        for event in events:
            await self.on_dispute_resolved(event)
