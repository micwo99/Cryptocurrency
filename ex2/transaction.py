import hashlib

from .utils import PublicKey, Signature, TxID
from typing import Optional


class Transaction:
    """Represents a transaction that moves a single coin
    A transaction with no source creates money. It will only be created by the miner of a block."""

    def __init__(self, output: PublicKey, tx_input: Optional[TxID], signature: Signature) -> None:
        # DO NOT change these field names.
        self.output: PublicKey = output
        # DO NOT change these field names.
        self.input: Optional[TxID] = tx_input
        # DO NOT change these field names.
        self.signature: Signature = signature

    def get_txid(self) -> TxID:
        """
        Returns the identifier of this transaction. This is the sha256 of the transaction contents.
        This function is used by the tests to compute the tx hash. Make sure to compute this every time 
        directly from the data in the transaction object, and not cache the result
        """
        tx = b"".join([self.output, self.input or b"", self.signature])
        hashed_tx = hashlib.sha256(tx).digest()
        return TxID(hashed_tx)

"""
Importing this file should NOT execute code. It should only create definitions for the objects above.
Write any tests you have in a different file.
You may add additional methods, classes and files but be sure no to change the signatures of methods
included in this template.
"""
