from typing import List
from blockchain.block import Block
import config

def validate_proof(block: Block, difficulty: int = config.MINING_DIFFICULTY) -> bool:
    """Check if the block's hash satisfies the proof-of-work target difficulty."""
    block_hash = block.calculate_hash()
    return block_hash.startswith('0' * difficulty)

def validate_block(block: Block, previous_block: Block, difficulty: int = config.MINING_DIFFICULTY) -> bool:
    """Validate a single block relative to its predecessor."""
    if block.index != previous_block.index + 1:
        return False
    if block.previous_hash != previous_block.hash:
        return False
    if not validate_proof(block, difficulty):
        return False
    if block.hash != block.calculate_hash():
        return False
    return True

def validate_chain(chain: List[Block], difficulty: int = config.MINING_DIFFICULTY) -> bool:
    """Validate an entire blockchain from the genesis block onward."""
    if not chain:
        return False
    
    # Genesis block verification
    genesis = chain[0]
    if genesis.index != 0:
        return False
    if genesis.previous_hash != "1":
        return False
    if genesis.hash != genesis.calculate_hash():
        return False
        
    for i in range(1, len(chain)):
        if not validate_block(chain[i], chain[i-1], difficulty):
            return False
    return True
