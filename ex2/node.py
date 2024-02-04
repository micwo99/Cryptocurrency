import secrets

from .utils import *
from .block import Block
from .transaction import Transaction
from typing import Set, Optional, List


class Node:
    def __init__(self) -> None:
        """Creates a new node with an empty mempool and no connections to others.
        Blocks mined by this node will reward the miner with a single new coin,
        created out of thin air and associated with the mining reward address"""

        self.connections: Set[Node] = set()
        self.mempool = list()
        self.utxo = list()
        self.blockchain: List[Block] = list()
        keys = gen_keys()
        self.private_key: PrivateKey = keys[0]
        self.public_key: PublicKey = keys[1]
        self.spents_tx = dict()

        self.reorg_chain = []
        self.reorg_spents_tx = dict()
        self.reorg_utxo = list()

    def connect(self, other: 'Node') -> None:
        """connects this node to another node for block and transaction updates.
        Connections are bi-directional, so the other node is connected to this one as well.
        Raises an exception if asked to connect to itself.
        The connection itself does not trigger updates about the mempool,
        but nodes instantly notify of their latest block to each other (see notify_of_block)"""
        if other == self:
            raise ValueError("Cannot connect to itself")
        else:
            self.connections.add(other)
            if self not in other.get_connections():
                other.connect(self)
            other.notify_of_block(self.get_latest_hash(), self)

    def disconnect_from(self, other: 'Node') -> None:
        """Disconnects this node from the other node. If the two were not connected, then nothing happens"""
        if other in self.connections:
            self.connections.remove(other)
            other.disconnect_from(self)

    def get_connections(self) -> Set['Node']:
        """Returns a set containing the connections of this node."""
        return self.connections

    def valid_tx_for_reorg(self, transaction: Transaction) -> bool:
        if not transaction.output or not transaction.signature:
            return False
        if transaction.input is None:
            return True
        input_transaction = None
        for utxo in self.reorg_utxo:
            if utxo.get_txid() == transaction.input:
                input_transaction = utxo
                break
        if input_transaction is None:
            return False
        if not verify(transaction.output + transaction.input, transaction.signature, input_transaction.output):
            return False
        return True

    def is_tx_valid(self, transaction: Transaction) -> bool:
        if not transaction.signature:
            return False

        find_tx = False
        utxos = self.get_utxo()
        for i in range(len(utxos)):
            if utxos[i].get_txid() == transaction.input:
                find_tx = utxos[i]

        if not find_tx:
            return False
        if not verify(transaction.output + transaction.input, transaction.signature, find_tx.output):
            return False

        if transaction.input not in [tx.get_txid() for tx in utxos]:
            return False

        for tx in self.mempool:
            if tx.input == transaction.input:
                return False
        if not transaction.input:
            return False
        return True

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
        if self.is_tx_valid(transaction):
            self.mempool.append(transaction)
            for node in self.connections:
                node.add_transaction_to_mempool(transaction)
            return True
        return False

    def check_block_in_blockchain(self, block_hash: BlockHash):
        if block_hash == GENESIS_BLOCK_PREV:
            return True
        for block in self.blockchain:
            if block.get_block_hash() == block_hash:
                return True
        return False

    def find_the_known_block(self, block_hash: BlockHash, sender: 'Node'):
        current_hash = block_hash
        new_chain = list()

        while not self.check_block_in_blockchain(current_hash):
            try:
                new_block = sender.get_block(current_hash)
                if not new_block.get_block_hash() == current_hash:
                    raise ValueError("have the same block hash ")
                new_chain.insert(0, new_block)
                prev_block = new_block.get_prev_block_hash()
                current_hash = prev_block
            except:

                return [], None

        return new_chain, current_hash

    def chain_until_block(self, block_hash):
        if self.blockchain:
            chain = []
            last_hash = self.blockchain[-1].get_block_hash()
            wanted_hash = block_hash
            while not last_hash == GENESIS_BLOCK_PREV and not wanted_hash == last_hash:
                block: Block = self.get_block(last_hash)
                chain.append(block)
                last_hash = block.get_prev_block_hash()
            return chain
        return []

    def remove_block(self, block: Block):

        to_removed_tx = [tx.get_txid() for tx in block.get_transactions()]
        self.reorg_utxo = [tx for tx in self.reorg_utxo if
                           tx.get_txid() not in to_removed_tx and tx.input not in to_removed_tx]
        for tx in block.get_transactions():
            if tx.input and self.reorg_spents_tx[tx.input]:
                self.reorg_utxo.append(self.reorg_spents_tx[tx.input])
        self.reorg_chain.remove(block)

    def valid_block(self, block: Block) -> bool:
        if len(block.get_transactions()) > BLOCK_SIZE:
            return False
        counter = 0
        for tx in block.get_transactions():
            if not tx.input:
                counter += 1
                continue
            if not self.valid_tx_for_reorg(tx):
                return False
        return counter == 1

    def add_chain_to_blockchain(self, new_chain):

        for block in new_chain:
            if not self.valid_block(block):
                return None
            self.reorg_chain.append(block)

            self.reorg_utxo.extend(block.get_transactions())
            new_tx = [transaction.input for transaction in block.get_transactions()]
            spent_tx = [tx for tx in self.reorg_utxo if tx.get_txid() in new_tx]
            if spent_tx:
                self.reorg_spents_tx.update({tx.get_txid(): tx for tx in spent_tx})
            self.reorg_utxo = [tx for tx in self.reorg_utxo if tx not in spent_tx]

    def chain_reorgs(self, new_chain, current_chain):
        cancels_txs = list()
        for block in current_chain:
            self.remove_block(block)
            cancels_txs.extend(block.get_transactions())
        self.add_chain_to_blockchain(new_chain)
        if len(self.blockchain) < len(self.reorg_chain):
            self.blockchain = self.reorg_chain
            self.utxo = self.reorg_utxo
            self.spents_tx = self.reorg_spents_tx
            prev_mempool = self.mempool[:]
            self.mempool = []
            self.mempool = [tx for tx in prev_mempool if self.is_tx_valid(tx)]
            for node in self.connections:
                node.notify_of_block(self.blockchain[-1].get_block_hash(), self)

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

        new_chain, known_block_hash = self.find_the_known_block(block_hash, sender)
        if new_chain:
            current_chain = self.chain_until_block(known_block_hash)
            self.reorg_chain = self.blockchain[:]
            self.reorg_utxo = self.utxo[:]
            self.reorg_spents_tx = self.spents_tx.copy()
            if len(current_chain) < len(new_chain):
                self.chain_reorgs(new_chain, current_chain)

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
        index = len(self.mempool)
        if len(self.mempool) > BLOCK_SIZE - 1:
            index = BLOCK_SIZE - 1

        miner_money = Transaction(self.get_address(), None, secrets.token_bytes(48))
        transactions_list = self.mempool[:index]
        transactions_list.append(miner_money)
        new_block = Block(self.get_latest_hash(),transactions_list)
        self.blockchain.append(new_block)

        for node in self.connections:
            node.notify_of_block(new_block.get_block_hash(), self)

        self.mempool = self.mempool[index:]

        self.utxo.extend(new_block.get_transactions())
        new_tx = [transaction.input for transaction in new_block.get_transactions()]
        spent_tx = [tx for tx in self.utxo if tx.get_txid() in new_tx]
        self.spents_tx.update({tx.get_txid(): tx for tx in spent_tx})
        self.utxo = [unspent_transaction for unspent_transaction in self.utxo if
                       unspent_transaction.get_txid() not in new_tx]
        return self.get_latest_hash()


    def get_block(self, block_hash: BlockHash) -> Block:
        """
        This function returns a block object given its hash.
        If the block doesnt exist, a ValueError is raised.
        """
        for block in self.blockchain:
            if block.get_block_hash() == block_hash:
                return block
        raise ValueError("the block doesnt exist")

    def get_latest_hash(self) -> BlockHash:
        """
        This function returns the last block hash known to this node (the tip of its current chain).
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
        return self.utxo

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
        mempool_inputs = [tx.input for tx in self.get_mempool()]
        coins = list()
        for tx in self.get_utxo():
            if self.get_address() == tx.output and tx.get_txid() not in mempool_inputs:
                coins.append(tx)
        for coin in coins:
            signature = sign(target+coin.get_txid(),self.private_key)
            tx = Transaction(target, coin.get_txid(),signature)
            self.add_transaction_to_mempool(tx)
            return tx
        return None


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
        balance = [tx for tx in self.utxo if tx.output == self.get_address()]
        return len(balance)

    def get_address(self) -> PublicKey:
        """
        This function returns the public address of this node (its public key).
        """
        return self.public_key


"""
Importing this file should NOT execute code. It should only create definitions for the objects above.
Write any tests you have in a different file.
You may add additional methods, classes and files but be sure no to change the signatures of methods
included in this template.
"""
