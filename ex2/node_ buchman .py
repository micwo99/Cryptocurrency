# self.mempool = []  # An empty list to store unconfirmed transactions
#         self.connections = []  # An empty list to store connections to other nodes
#         self.mining_reward_address = "your_reward_address_here"  # The address where mining rewards will be sent
import os

from .utils import *
from .block import Block
from .transaction import Transaction
from typing import Set, Optional, List


class Node:
    def __init__(self) -> None:
        """
        Creates a new node with an empty mempool and no connections to others.
        Blocks mined by this node will reward the miner with a single new coin,
        created out of thin air and associated with the mining reward address.
        """

        self.mempool = []
        self.connections = set()
        self.chain = []
        self.utxo = set()

        genesis_block = Block.mine_genesis_block()
        self.chain.append(genesis_block)
        self.update_utxo(genesis_block)

    # You can add other methods for the Node class here, such as methods for mining, broadcasting transactions, etc.


    def connect(self, other: 'Node') -> None:
        """connects this node to another node for block and transaction updates.
        Connections are bi-directional, so the other node is connected to this one as well.
        Raises an exception if asked to connect to itself.
        The connection itself does not trigger updates about the mempool,
        but nodes instantly notify of their latest block to each other (see notify_of_block)"""
        if other == self:
            raise Exception("Cannot connect to itself")

        self.connections.add(other)
        other.connections.add(self)

        self.notify_of_block(self.get_latest_hash(), other)

    def disconnect_from(self, other: 'Node') -> None:
        """Disconnects this node from the other node. If the two were not connected, then nothing happens"""
        if other in self.connections:
            self.connections.remove(other)
            other.connections.remove(self)

    def get_connections(self) -> Set['Node']:
        """Returns a set containing the connections of this node."""
        return self.connections

    def add_transaction_to_mempool(self, transaction: Transaction) -> bool:
        """
        This function inserts the given transaction to the mempool.
        It will return False iff any of the following conditions hold:
        (i) the transaction is invalid (the signature fails)
        (ii) the source doesn't have the coin that it tries to spend
        (iii) there is contradicting tx in the mempool.

        If the transaction is added successfully, then it is also sent to neighboring nodes.
        Transactions that create money (with no inputs) are not placed in the mempool, and not propagated. 
        """
        if transaction.is_valid(self.utxo) and transaction not in self.mempool:
            self.mempool.append(transaction)
            for connection in self.connections:
                connection.add_transaction_to_mempool(transaction)
            return True
        return False


    def notify_of_block(self, block_hash: BlockHash, sender: 'Node') -> None:
        """This method is used by a node's connection to inform it that it has learned of a
        new block (or created a new block). If the block is unknown to the current Node, The block is requested.
        We assume the sender of the message is specified, so that the node can choose to request this block if
        it wishes to do so.
        (if it is part of a longer unknown chain, these blocks are requested as well, until reaching a known block).
        Upon receiving new blocks, they are processed and and checked for validity (check all signatures, hashes,
        block size , etc).
        If the block is on the longest chain, the mempool and utxo change accordingly (ties, i.e., chains of similar length to that of this node are not adopted).
        If the block is indeed the tip of the longest chain,
        a notification of this block is sent to the neighboring nodes of this node.
        (no need to notify of previous blocks -- the nodes will fetch them if needed)

        A reorg may be triggered by this block's introduction. In this case the utxo is rolled back to the split point,
        and then rolled forward along the new branch. Be careful -- the new branch may contain invalid blocks. These and blocks that point to them should not be accepted to the blockchain (but earlier valid blocks may still form a longer chain)
        the mempool is similarly emptied of transactions that cannot be executed now.
        transactions that were rolled back and can still be executed are re-introduced into the mempool if they do
        not conflict.
        """

        if block_hash not in self.known_blocks:
            block = sender.get_block(block_hash)
            if self._validate_block(block):
                self.known_blocks[block_hash] = block
                self._update_utxo(block)
                self._remove_transactions_from_mempool(block)

                prev_block_hash = block.get_prev_block_hash()
                if prev_block_hash not in self.known_blocks:
                    self.notify_of_block(prev_block_hash, sender)

                # Handle chain reorganization
                current_chain_length = self._get_chain_length(self.latest_block_hash)
                new_chain_length = self._get_chain_length(block_hash)

                if new_chain_length > current_chain_length:
                    self.latest_block_hash = block_hash

                # Notify neighbors of the new block
                for connection in self.connections:
                    if connection != sender:
                        connection.notify_of_block(block_hash, self)


    def mine_block(self) -> BlockHash:
        """"
        This function allows the node to create a single block.
        The block should contain BLOCK_SIZE transactions (unless there aren't enough in the mempool). Of these,
        BLOCK_SIZE-1 transactions come from the mempool and one addtional transaction will be included that creates
        money and adds it to the address of this miner.
        Money creation transactions have None as their input, and instead of a signature, contain 48 random bytes.
        If a new block is created, all connections of this node are notified by calling their notify_of_block() method.
        The method returns the new block hash.
        """

        # Create a money creation transaction
        money_creation_signature = os.urandom(64)
        money_creation_tx = Transaction(self.public_key, None, money_creation_signature)

        # Select BLOCK_SIZE - 1 transactions from the mempool
        selected_transactions = self.mempool[:BLOCK_SIZE - 1]

        # Create the block with the selected transactions and the money creation transaction
        transactions = [money_creation_tx] + selected_transactions
        prev_block_hash = self.get_latest_hash()
        new_block = Block(prev_block_hash, transactions)

        # Add the new block to the blockchain
        block_hash = new_block.get_block_hash()
        self.blockchain[block_hash] = new_block

        # Update the utxo and mempool
        self._update_utxo(new_block)
        self._remove_transactions_from_mempool(new_block)

        # Notify all connections of the new block
        for connection in self.connections:
            connection.notify_of_block(block_hash, self)

        return block_hash


    def get_block(self, block_hash: BlockHash) -> Block:
        """
        This function returns a block object given its hash.
        If the block doesnt exist, a ValueError is raised.
        """
        for block in self.chain:
            if block.hash == block_hash:
                return block
        return None

    def get_latest_hash(self) -> BlockHash:
        """
        This function returns the last block hash known to this node (the tip of its current chain).
        """
        return self.chain[-1].hash

    def get_mempool(self) -> List[Transaction]:
        """
        This function returns the list of transactions that didn't enter any block yet.
        """
        return self.mempool

    def get_utxo(self) -> List[Transaction]:
        """
        This function returns the list of unspent transactions.
        """
        return list(self.utxo)

    # ------------ Formerly wallet methods: -----------------------

    def create_transaction(self, target: PublicKey) -> Optional[Transaction]:
        """
        This function returns a signed transaction that moves an unspent coin to the target.
        It chooses the coin based on the unspent coins that this node has.
        If the node already tried to spend a specific coin, and such a transaction exists in its mempool,
        but it did not yet get into the blockchain then it should'nt try to spend it again (until clear_mempool() is
        called -- which will wipe the mempool and thus allow to attempt these re-spends).
        The method returns None if there are no outputs that have not been spent already.

        The transaction is added to the mempool (and as a result is also published to neighboring nodes)
        """
        # utxo = self.get_utxo()
        # available_coins = [coin for coin in utxo if coin.recipient == self.get_address()]
        #
        # # Filter out coins that are already in the mempool
        # for tx in self.get_mempool():
        #     available_coins = [coin for coin in available_coins if coin != tx.output]
        #
        # if not available_coins:
        #     return None
        #
        # chosen_coin = available_coins[0]
        # new_tx = Transaction(self.get_address(), target, chosen_coin)
        # new_tx.sign(self.private_key)
        #
        # if self.add_transaction_to_mempool(new_tx):
        #     for connection in self.get_connections():
        #         connection.add_transaction_to_mempool(new_tx)
        #     return new_tx
        # else:
        #     return None

        unspent_coins = self.get_unspent_coins()
        mempool_txids = {tx.get_txid() for tx in self.mempool}

        for txid, output in unspent_coins.items():
            if txid not in mempool_txids:
                signature = self.sign(txid)
                new_transaction = Transaction(target, txid, signature)

                self.mempool.append(new_transaction)
                self._propagate_transaction(new_transaction)

                return new_transaction

        return None

    def _propagate_transaction(self, transaction: Transaction) -> None:
        for connection in self.connections:
            connection.notify_of_transaction(transaction, self)


    def clear_mempool(self) -> None:
            """
            Clears the mempool of this node. All transactions waiting to be entered into the next block are gone.
            """
            self.mempool.clear()


    def get_balance(self) -> int:
            """
            This function returns the number of coins that this node owns according to its view of the blockchain.
            Coins that the node owned and sent away will still be considered as part of the balance until the spending
            transaction is in the blockchain.
            """
            utxo = self.get_utxo()
            balance = sum([coin.amount for coin in utxo if coin.recipient == self.get_address()])
            return balance

    def get_address(self) -> PublicKey:
        """
        This function returns the public address of this node (its public key).
        """
        raise NotImplementedError()


    def update_utxo(self, block: Block) -> None:
        for transaction in block.transactions:
            if transaction.input_tx is not None:
                self.utxo.discard(transaction.input_tx)
            self.utxo.add(transaction)


    def update_mempool(self, block: Block) -> None:
        for transaction in block.transactions:
            if transaction in self.mempool:
                self.mempool.remove(transaction)


    def is_new_block(self, block_hash: BlockHash) -> bool:
        return block_hash not in self.blockchain

    def _validate_block(self, block: Block) -> bool:
        block_size_limit = 1000  # Set the block size limit

        # Check if block size exceeds the limit
        if len(block.get_transactions()) > block_size_limit:
            return False

        # Check for malformed transactions, double spends, or invalid money creation transactions
        money_creation_tx_count = 0
        spent_txids = set()
        for tx in block.get_transactions():
            if tx.input is None:  # Money creation transaction
                money_creation_tx_count += 1
            else:
                if tx.input in spent_txids:  # Double spend
                    return False
                spent_txids.add(tx.input)

        if money_creation_tx_count != 1:  # Invalid number of money creation transactions
            return False

        # If all checks pass, the block is valid
        return True

    def _update_utxo(self, block: Block) -> None:
        for tx in block.get_transactions():
            if tx.input is not None:
                self.utxo.remove(tx.input)
            new_txid = tx.get_txid()
            self.utxo.add(new_txid)

    def _remove_transactions_from_mempool(self, block: Block) -> None:
        for tx in block.get_transactions():
            if tx in self.mempool:
                self.mempool.remove(tx)

    def _get_chain_length(self, block_hash: BlockHash) -> int:
        length = 0
        current_block_hash = block_hash

        while current_block_hash is not None:
            current_block = self.get_block(current_block_hash)
            current_block_hash = current_block.get_prev_block_hash()
            length += 1

        return length


    def notify_of_transaction(self, transaction: Transaction, sender: 'Node') -> None:
        """This method is used by a node's connection to inform it that it has learned of a
        new transaction. If the transaction is unknown to the current Node and is valid, it's
        added to the mempool and propagated to other connected nodes.
        """
        if transaction.get_txid() not in self.mempool:
            if self.add_transaction_to_mempool(transaction):
                for node in self.connections:
                    if node != sender:
                        node.notify_of_transaction(transaction, self)

"""
Importing this file should NOT execute code. It should only create definitions for the objects above.
Write any tests you have in a different file.
You may add additional methods, classes and files but be sure no to change the signatures of methods
included in this template.
"""
