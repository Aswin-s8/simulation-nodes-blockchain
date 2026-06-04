# Blockchain Simulation Project Architecture

This document describes how each file in the `blockchain-network` project works and how they interact, written in simple terms for basic Python learners.

---

## Overview: The Post Office Analogy

Imagine this network as **5 independent post offices (nodes)**. Each post office maintains its own copy of a **ledger book (the blockchain)** containing lists of money transfers. To prevent anyone from cheating, they must follow a set of strict rules (consensus) and immediately notify each other (networking) about new entries or blocks.

```
                      +-----------------------------+
                      |          EACH NODE          |
                      |                             |
                      |    [app.py (Receptionist)]  |  <--- Web requests / Users
                      |            |                |
                      |            v                |
                      |  [blockchain.py (Engine)]   |
                      |      /     |        \       |
                      |     /      |         \      |
                      |    v       v          v     |
                      | [tx.py] [block.py] [con.py] |
                      |            |                |
                      |            v                |
                      |   [networking.py (P2P)]     |  <---> Other Nodes (TCP Sockets)
                      +-----------------------------+
```

---

## File Explanations

### 1. `config.py` (The Settings File)
* **What it does:** Reads configuration settings from environmental variables (like node names, network ports, mining difficulty, and the folder for saving blocks).
* **Key Concept:** Uses Python's `os.getenv` to fetch parameters set in `docker-compose.yml` or defaults to standard values if they aren't provided.

### 2. `blockchain/transaction.py` (A Ledger Entry)
* **What it does:** Represents a single coin transfer from a sender to a recipient. 
* **Key features:**
  * Stores `sender`, `recipient`, and `amount`.
  * Computes a unique `transaction_id` using SHA-256 hashing. Hashing is like generating a unique fingerprint of the transaction's contents. If someone changes the amount by even 1 cent, the fingerprint changes completely.
  * Contains helper functions `to_dict()` and `from_dict()` so the transaction can be converted to JSON and sent over the network.

### 3. `blockchain/block.py` (A Page in the Ledger Book)
* **What it does:** A block collects multiple transactions together. 
* **Key features:**
  * Stores its block position (`index`), timestamp, a list of transactions, and the hash of the previous page (`previous_hash`). This chaining prevents any historic page from being altered.
  * Contains a `proof` (a special number solved during mining).
  * Hashing the block creates its unique identity. If any transaction inside the block is tampered with, the block's hash changes, breaking the link to the next block.

### 4. `blockchain/consensus.py` (The Referee / Rules)
* **What it does:** Defines what makes a block or a chain valid. It contains the mathematical checks.
* **Key features:**
  * Checks if a block's hash matches its calculated hash.
  * Checks if the hash starts with the target number of zeros (e.g. `"0000"` for difficulty 4).
  * Validates the linkages of the entire chain from the genesis block (first block) to the end.

### 5. `blockchain/blockchain.py` (The Ledger Book Manager)
* **What it does:** This is the core storage engine. It holds the active `chain` (list of blocks) and the `pending_transactions` (transactions submitted but not yet mined).
* **Key features:**
  * **Thread Safety:** Uses a Python lock (`self.lock`) to ensure multiple P2P connections or API requests can read/write the blockchain state safely without conflicts.
  * **Mining:** Runs the Proof-of-Work puzzle loop. To keep API requests responsive, mining is performed outside the main lock. Once a puzzle is solved, the lock is acquired to safely append the block.
  * **Persistence:** Saves the state to `/data/blockchain.json` and loads it when starting.

### 6. `blockchain/networking.py` (The Postman)
* **What it does:** Establishes direct P2P connections using TCP sockets.
* **Key features:**
  * **Discovery:** Non-bootstrap nodes connect to `node1` (bootstrap) on start, register their connection details, get list of active nodes, and connect to them.
  * **Framing:** TCP streams can fragment data. To prevent parsing half-broken JSON, this file prefixes every message with a 4-byte length header indicating the size of the incoming data.
  * **Synchronization:** If a node receives a block from the future (higher index), it requests the full chain from that peer, checks its validity using `consensus.py`, and replaces its local chain if it's longer.

### 7. `app.py` (The receptionist / REST API)
* **What it does:** Runs a **Flask web server** so you can interact with the node using HTTP requests.
* **Endpoints:**
  * `GET /chain`: Returns the full blockchain.
  * `POST /transaction`: Accepts a transaction payload, stores it in pending, and propagates it to all peers.
  * `POST /mine`: Triggers mining of pending transactions.
  * `GET /peers`: Lists who this node is communicating with.
  * `GET /status`: Quick status summary of the node.

### 8. `Dockerfile` & `docker-compose.yml` (The Virtual Blueprint)
* **What they do:** 
  * `Dockerfile` tells Docker how to install Python, copy the files, and run `app.py` inside a isolated container.
  * `docker-compose.yml` launches 5 of these containers simultaneously. It links them together on a virtual network (`blockchain-net`) so they can speak to each other by name (e.g., `node1`), maps their ports to your physical computer (`5001`-`5005`), and configures persistent folders (volumes) so data is saved even if containers are destroyed.
