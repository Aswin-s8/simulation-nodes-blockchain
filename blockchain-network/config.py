import os
import uuid

# Node configuration
NODE_ID = os.getenv("NODE_ID", f"node_{uuid.uuid4().hex[:8]}")
HTTP_PORT = int(os.getenv("HTTP_PORT", "5000"))
P2P_PORT = int(os.getenv("P2P_PORT", "6000"))

# P2P Network configuration
# For non-bootstrap nodes, this should be set to the bootstrap node's container name/IP and P2P port: e.g., "node1:6000"
BOOTSTRAP_PEER = os.getenv("BOOTSTRAP_PEER", None)
IS_BOOTSTRAP = os.getenv("IS_BOOTSTRAP", "false").lower() == "true" or NODE_ID == "node1"

# Persistence configuration
DATA_DIR = os.getenv("DATA_DIR", "./data")

# Ensure the data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Blockchain parameters
MINING_DIFFICULTY = 4  # Number of leading zeros for PoW
MINING_SENDER = "MINING_REWARD"
MINING_REWARD = 10.0
