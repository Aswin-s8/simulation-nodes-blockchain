import os
import json
import threading
from typing import List, Optional
from blockchain.block import Block
from blockchain.transaction import Transaction
from blockchain import consensus
import config

class Blockchain:
    def __init__(self):
        self.difficulty = config.MINING_DIFFICULTY
        self.chain_file = os.path.join(config.DATA_DIR, "blockchain.json")
        self.lock = threading.Lock()
        
        self.chain: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        
        # Load from disk if exists, otherwise create genesis block
        self.load_chain()

    def create_genesis_block(self):
        """Initialize blockchain with Genesis Block."""
        genesis_block = Block(
            index=0,
            transactions=[],
            previous_hash="1",
            proof=100,
            timestamp=1700000000.0  # Fixed timestamp so all nodes share the identical genesis hash
        )
        self.chain = [genesis_block]
        self.save_chain()

    def get_last_block(self) -> Block:
        return self.chain[-1]

    def add_transaction(self, sender: str, recipient: str, amount: float) -> int:
        """Adds a new transaction to the list of pending transactions."""
        tx = Transaction(sender=sender, recipient=recipient, amount=amount)
        with self.lock:
            # Prevent adding duplicates
            if any(p_tx.transaction_id == tx.transaction_id for p_tx in self.pending_transactions):
                return self.get_last_block().index + 1
            self.pending_transactions.append(tx)
            self.save_chain()
            return self.get_last_block().index + 1

    def add_raw_transaction(self, tx: Transaction) -> bool:
        """Adds a Transaction object directly (used for P2P propagation)."""
        with self.lock:
            # Check if transaction is already in pending or in chain
            if any(p_tx.transaction_id == tx.transaction_id for p_tx in self.pending_transactions):
                return False
            for block in self.chain:
                if any(b_tx.transaction_id == tx.transaction_id for b_tx in block.transactions):
                    return False
            self.pending_transactions.append(tx)
            self.save_chain()
            return True

    def mine_pending_transactions(self, miner_address: str) -> Optional[Block]:
        """
        Mines a new block containing pending transactions.
        Performs mining outside the main lock to avoid blocking other API calls.
        """
        # 1. Take a snapshot of state needed for mining
        with self.lock:
            last_block = self.get_last_block()
            index = last_block.index + 1
            previous_hash = last_block.hash
            
            # Create a reward transaction for the miner
            reward_tx = Transaction(
                sender=config.MINING_SENDER,
                recipient=miner_address,
                amount=config.MINING_REWARD
            )
            
            # Combine reward and current pending transactions
            tx_pool = [reward_tx] + list(self.pending_transactions)

        # 2. Mine the block outside the lock
        candidate_block = Block(
            index=index,
            transactions=tx_pool,
            previous_hash=previous_hash,
            proof=0
        )
        
        self.proof_of_work(candidate_block)
        
        # 3. Try to append to the chain
        with self.lock:
            # Double check that the last block hasn't changed while we were mining
            current_last_block = self.get_last_block()
            if current_last_block.hash != previous_hash:
                # The chain moved ahead! This mined block is stale.
                return None
            
            self.chain.append(candidate_block)
            
            # Remove mined transactions from pending pool
            mined_ids = {tx.transaction_id for tx in tx_pool}
            self.pending_transactions = [
                tx for tx in self.pending_transactions if tx.transaction_id not in mined_ids
            ]
            
            self.save_chain()
            return candidate_block

    def proof_of_work(self, block: Block) -> int:
        """Find proof of work nonce."""
        block.proof = 0
        while not consensus.validate_proof(block, self.difficulty):
            block.proof += 1
        block.hash = block.calculate_hash()
        return block.proof

    def valid_proof(self, block: Block) -> bool:
        """Check if block's hash satisfies the difficulty target."""
        return consensus.validate_proof(block, self.difficulty)

    def validate_block(self, block: Block, previous_block: Block) -> bool:
        """Validate a block's structure and proof of work relative to a previous block."""
        return consensus.validate_block(block, previous_block, self.difficulty)

    def validate_chain(self, chain: List[Block]) -> bool:
        """Validates a complete blockchain."""
        return consensus.validate_chain(chain, self.difficulty)

    def replace_chain(self, new_blocks: List[Block]) -> bool:
        """Replace local chain with a longer, valid chain."""
        with self.lock:
            if len(new_blocks) <= len(self.chain):
                return False
            if not self.validate_chain(new_blocks):
                return False
                
            self.chain = new_blocks
            
            # Clean up pending transactions that are already in the new chain
            chain_tx_ids = set()
            for block in self.chain:
                for tx in block.transactions:
                    chain_tx_ids.add(tx.transaction_id)
            
            self.pending_transactions = [
                tx for tx in self.pending_transactions if tx.transaction_id not in chain_tx_ids
            ]
            
            self.save_chain()
            return True

    def save_chain(self):
        """Save blockchain state to disk."""
        data = {
            "chain": [block.to_dict() for block in self.chain],
            "pending_transactions": [tx.to_dict() for tx in self.pending_transactions]
        }
        with open(self.chain_file, "w") as f:
            json.dump(data, f, indent=4)

    def load_chain(self):
        """Load blockchain state from disk."""
        if not os.path.exists(self.chain_file):
            self.create_genesis_block()
            return
            
        try:
            with open(self.chain_file, "r") as f:
                data = json.load(f)
            
            self.chain = [Block.from_dict(b) for b in data.get("chain", [])]
            self.pending_transactions = [Transaction.from_dict(tx) for tx in data.get("pending_transactions", [])]
            
            if not self.chain or not self.validate_chain(self.chain):
                # If disk data is invalid, recreate genesis
                self.create_genesis_block()
        except Exception as e:
            print(f"Error loading chain: {e}. Reinitializing.")
            self.create_genesis_block()
