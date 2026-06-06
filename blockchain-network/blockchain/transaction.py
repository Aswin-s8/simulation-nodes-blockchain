import hashlib
import time

class Transaction:
    def __init__(self, sender: str, recipient: str, amount: float, timestamp: float = None, transaction_id: str = None, data: dict = None):
        self.sender = sender
        self.recipient = recipient
        self.amount = float(amount)
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.data = data if data is not None else {}
        self.transaction_id = transaction_id if transaction_id is not None else self.calculate_id()

    def calculate_id(self) -> str:
        """Calculate the SHA-256 hash of the transaction to serve as its unique ID."""
        import json
        data_serialized = json.dumps(self.data, sort_keys=True)
        payload = f"{self.sender}:{self.recipient}:{self.amount}:{self.timestamp}:{data_serialized}"
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    def to_dict(self) -> dict:
        """Convert the transaction instance to a dictionary for JSON serialization."""
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "transaction_id": self.transaction_id,
            "data": self.data
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Transaction':
        """Create a Transaction instance from a dictionary."""
        return cls(
            sender=data["sender"],
            recipient=data["recipient"],
            amount=data["amount"],
            timestamp=data.get("timestamp"),
            transaction_id=data.get("transaction_id"),
            data=data.get("data")
        )

    def __repr__(self) -> str:
        return f"<Transaction {self.transaction_id[:8]} from={self.sender} to={self.recipient} amt={self.amount}>"
