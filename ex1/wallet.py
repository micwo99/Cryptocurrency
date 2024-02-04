from .utils import *
from .transaction import Transaction
from .bank import Bank
from typing import Optional


class Wallet:
    def __init__(self) -> None:
        """This function generates a new wallet with a new private key."""
        generator=gen_keys()
        self.private_key: PrivateKey = generator[0]
        self.public_key : PublicKey= generator[1]
        self.utxo  = {}
        self.balance : int =0
        self.freeze_transaction = set()
        self.last_hash: BlockHash = GENESIS_BLOCK_PREV

    def update(self, bank: Bank) -> None:
        """
        This function updates the balance allocated to this wallet by querying the bank.
        Don't read all of the bank's utxo, but rather process the blocks since the last update one at a time.
        For this exercise, there is no need to validate all transactions in the block.
        """
        end = bank.get_latest_hash()
        curr = self.last_hash
        while end != curr:
            last_block = bank.get_block(end)
            for tx in last_block.get_transactions():
                if tx.input in self.utxo:
                    self.utxo.pop(tx.input)
                if self.public_key == tx.output and tx.get_txid() not in self.freeze_transaction :
                        self.utxo[tx.get_txid()] = tx
                if self.public_key == tx.output and tx.get_txid() in self.freeze_transaction:
                        self.freeze_transaction.remove(tx.get_txid())
            end = last_block.get_prev_block_hash()
        self.balance=len(self.utxo)
        self.last_hash = bank.get_latest_hash()


    def create_transaction(self, target: PublicKey) -> Optional[Transaction]:
        """
        This function returns a signed transaction that moves an unspent coin to the target.
        It chooses the coin based on the unspent coins that this wallet had since the last update.
        If the wallet already spent a specific coin, but that transaction wasn't confirmed by the
        bank just yet (it still wasn't included in a block) then the wallet  should'nt spend it again
        until unfreeze_all() is called. The method returns None if there are no unspent outputs that can be used.
        """
        if all(txid in self.freeze_transaction for txid in self.utxo):  # all UTXOs are frozen
            return None
        else:
            txid = next(filter(lambda k: k not in self.freeze_transaction, self.utxo.keys()))
            transaction = Transaction(target, txid, None)
            transaction.signature = sign(transaction.input+transaction.output, self.private_key)
            self.freeze_transaction.add(txid)
            return transaction 

    def unfreeze_all(self) -> None:
        """
        Allows the wallet to try to re-spend outputs that it created transactions for (unless these outputs made it into the blockchain).
        """
        self.freeze_transaction = set()

    def get_balance(self) -> int:
        """
        This function returns the number of coins that this wallet has.
        It will return the balance according to information gained when update() was last called.
        Coins that the wallet owned and sent away will still be considered as part of the balance until the spending
        transaction is in the blockchain.
        """
        return self.balance

    def get_address(self) -> PublicKey:
        """
        This function returns the public address of this wallet (see the utils module for generating keys).
        """
        return self.public_key
