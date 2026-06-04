import hashlib
import json
import time
from typing import List
from blockchain.transaction import Transaction

class Block:
    def __init__(self, index: int, transactions: List[Transaction], previous_hash: str, proof: int = 0, timestamp: float = None, hash: str = None):
        self.index = index
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.transactions = transactions
        self.proof = proof
        self.previous_hash = previous_hash
        self.hash = hash if hash is not None else self.calculate_hash()

    def calculate_hash(self) -> str:
        """Calculate the SHA-256 hash of the block contents."""
        # Convert transactions to their dictionary format and sort keys to maintain consistency
        tx_dicts = [tx.to_dict() for tx in self.transactions]
        tx_serialized = json.dumps(tx_dicts, sort_keys=True)
        
        payload = f"{self.index}:{self.timestamp}:{tx_serialized}:{self.proof}:{self.previous_hash}"
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    def to_dict(self) -> dict:
        """Convert the block instance to a dictionary for JSON serialization."""
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "proof": self.proof,
            "previous_hash": self.previous_hash,
            "hash": self.hash
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Block':
        """Create a Block instance from a dictionary representation."""
        transactions = [Transaction.from_dict(tx) for tx in data.get("transactions", [])]
        return cls(
            index=data["index"],
            transactions=transactions,
            previous_hash=data["previous_hash"],
            proof=data["proof"],
            timestamp=data["timestamp"],
            hash=data.get("hash")
        )

    def __repr__(self) -> str:
        return f"<Block #{self.index} hash={self.hash[:8]} prev={self.previous_hash[:8]} txs={len(self.transactions)}>"
