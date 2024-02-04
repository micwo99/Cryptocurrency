import hashlib

from .utils import BlockHash
from .transaction import Transaction
from typing import List


class Block:
    """This class represents a block."""

    # implement __init__ as you see fit.
    def __init__(self,  previous: BlockHash,transactions_list: List[Transaction]):
        self.transactions_list: List[Transaction] = transactions_list
        self.previous_block: BlockHash = previous

    def get_block_hash(self) -> BlockHash:
        """Gets the hash of this block. 
        This function is used by the tests. Make sure to compute the result from the data in the block every time 
        and not to cache the result"""
        block_to_hash = self.previous_block
        for transaction in self.transactions_list:
            block_to_hash += transaction.get_txid()
        return BlockHash(hashlib.sha256(block_to_hash).digest())

    def get_transactions(self) -> List[Transaction]:
        """
        returns the list of transactions in this block.
        """
        return self.transactions_list

    def get_prev_block_hash(self) -> BlockHash:
        """Gets the hash of the previous block"""
        return self.previous_block
