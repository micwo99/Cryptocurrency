import secrets

from .utils import BlockHash, PublicKey, GENESIS_BLOCK_PREV, verify
from .transaction import Transaction
from .block import Block
from typing import List


class Bank:
    def __init__(self) -> None:
        """Creates a bank with an empty blockchain and an empty mempool."""
        self.mempool: List[Transaction] = list()
        self.blockchain: List[Block] = list()

    def add_transaction_to_mempool(self, transaction: Transaction) -> bool:
        """
        This function inserts the given transaction to the mempool.
        It will return False iff one of the following conditions hold:
        (i) the transaction is invalid (the signature fails)
        (ii) the source doesn't have the coin that he tries to spend
        (iii) there is contradicting tx in the mempool.
        (iv) there is no input (i.e., this is an attempt to create money from nothing)
        """
        if not transaction.signature:
            return False

        find_tx = False
        utxos=self.get_utxo()
        for i in range(len(utxos)):
            if utxos[i].get_txid() == transaction.input:
                find_tx = utxos[i]

        if not find_tx:
            return False
        if not verify(transaction.input + transaction.output, transaction.signature, find_tx.output):
            return False

        if transaction.input not in [tx.get_txid() for tx in utxos]:
            return False

        for tx in self.mempool:
            if tx.input == transaction.input:
                return False
        if not transaction.input:
            return False

        self.mempool.append(transaction)
        return True

    def end_day(self, limit: int = 10) -> BlockHash:
        """
        This function tells the bank that the day ended,
        and that the first `limit` transactions in the mempool should be committed to the blockchain.
        If there are fewer than 'limit' transactions in the mempool, a smaller block is created.
        If there are no transactions, an empty block is created. The hash of the block is returned.
        """
        if len(self.blockchain) == 0:
            previous = GENESIS_BLOCK_PREV
        else:
            previous = self.get_latest_hash()

        if len(self.mempool) == 0:
            block = Block(list(), previous)
            self.blockchain.append(block)
            return block.get_block_hash()
        elif len(self.mempool)<limit:
            block = Block(self.mempool, previous)
            self.mempool = list()
            self.blockchain.append(block)
            return block.get_block_hash()
        else:
            block = Block(self.mempool[:limit], previous)
            self.mempool = self.mempool[limit:]
            self.blockchain.append(block)
            return block.get_block_hash()

    def get_block(self, block_hash: BlockHash) -> Block:
        """
        This function returns a block object given its hash. If the block doesnt exist, an exception is thrown..
        """
        for block in self.blockchain:
            if block.get_block_hash() == block_hash:
                return block
        raise ValueError("the block isn't in the blockchain")

    def get_latest_hash(self) -> BlockHash:
        """
        This function returns the hash of the last Block that was created by the bank.
        """
        if len(self.blockchain) == 0:
            return GENESIS_BLOCK_PREV
        last_block = self.blockchain[len(self.blockchain) - 1]
        return last_block.get_block_hash()

    def get_mempool(self) -> List[Transaction]:
        """
        This function returns the list of transactions that didn't enter any block yet.
        """
        return self.mempool

    def get_utxo(self) -> List[Transaction]:
        """
        This function returns the list of unspent transactions.
        """
        transactions = []
        spent = set()
        for block in self.blockchain:
            for transaction in block.get_transactions():
                transactions.append(transaction)

                if transaction.input is not None:
                    spent.add(transaction.input)

        unspent = [tx for tx in transactions if tx.get_txid() not in spent]

        return unspent



    def create_money(self, target: PublicKey) -> None:
        """
        This function inserts a transaction into the mempool that creates a single coin out of thin air. Instead of a signature,
        this transaction includes a random string of 48 bytes (so that every two creation transactions are different).
        This function is a secret function that only the bank can use (currently for tests, and will make sense in a later exercise).
        """
        transaction = Transaction(target, None, secrets.token_bytes(48))
        self.mempool.append(transaction)
