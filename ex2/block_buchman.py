import hashlib

from .utils import BlockHash
from .transaction import Transaction
from typing import List


class Block:
    """This class represents a block."""

    # implement __init__ as you see fit.

    def __init__(self, prev_block_hash: BlockHash, transactions: List[Transaction], nonce: int):
        self.prev_block_hash = prev_block_hash
        self.transactions = transactions
        self.nonce = nonce


    def get_block_hash(self) -> BlockHash:
        """Gets the hash of this block. 
        This function is used by the tests. Make sure to compute the result from the data in the block every time 
        and not to cache the result"""
        content = str(self.prev_block_hash) + ''.join([str(tx) for tx in self.transactions]) + str(self.nonce)
        return hashlib.sha256(content.encode('utf-8')).hexdigest()


    def get_transactions(self) -> List[Transaction]:
        """
        returns the list of transactions in this block.
        """
        return self.transactions

    def get_prev_block_hash(self) -> BlockHash:
        """Gets the hash of the previous block"""
        return self.prev_block_hash

    @staticmethod
    def mine_genesis_block() -> 'Block':
        # You should replace this with the appropriate code to create the genesis block,
        # which will have specific transactions and a predefined nonce.
        return Block(None, [], 0)

    @staticmethod
    def mine(prev_block_hash: BlockHash, transactions: List[Transaction], miner_address) -> 'Block':
        transactions.append(Transaction.create_mining_reward(miner_address))
        nonce = 0
        while True:
            block = Block(prev_block_hash, transactions, nonce)
            block_hash = block.get_block_hash()
            if block_hash.startswith('0000'):  # Adjust the difficulty as needed
                break
            nonce += 1
        return block

    def is_valid(self, utxo) -> bool:
        # Implement validation checks for the block, including transaction validation,
        # and checking if the block hash starts with the required number of zeros.
        block_hash = self.get_block_hash()
        if not block_hash.startswith('0000'):  # Adjust the difficulty as needed
            return False

        for transaction in self.transactions:
            if not transaction.is_valid(utxo):
                return False

        return True

    def contains_money_creation(self) -> bool:
        money_creation_count = sum(tx.is_money_creation() for tx in self.transactions)
        return money_creation_count == 1