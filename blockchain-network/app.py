from flask import Flask, jsonify, request
import atexit
from blockchain.blockchain import Blockchain
from blockchain.networking import P2PNetwork
from blockchain.contracts import ContractVM
import config

app = Flask(__name__, static_folder='static', static_url_path='')

# Initialize Core Blockchain engine
blockchain = Blockchain()

# Initialize and start P2P Node networking
p2p = P2PNetwork(blockchain)
p2p.start()

# Clean shutdown of P2P threads on exit
@atexit.register
def shutdown():
    p2p.stop()

@app.after_request
def after_request(response):
    """Enable CORS headers for cross-node browser communication."""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/', methods=['GET'])
def index():
    """Serve the web dashboard frontend."""
    return app.send_static_file('index.html')

@app.route('/chain', methods=['GET'])
def get_chain():
    """Retrieve the full blockchain from this node."""
    with blockchain.lock:
        chain_data = [block.to_dict() for block in blockchain.chain]
        response = {
            "chain": chain_data,
            "length": len(chain_data)
        }
    return jsonify(response), 200

@app.route('/transaction', methods=['POST'])
def new_transaction():
    """Create a new transaction on this node and propagate it to all other peers."""
    values = request.get_json()
    if not values:
        return jsonify({"message": "Invalid JSON format"}), 400
        
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return jsonify({"message": "Missing required fields: sender, recipient, amount"}), 400
    
    # Add transaction to the local pool (including custom data if present)
    next_block_index = blockchain.add_transaction(
        sender=values['sender'],
        recipient=values['recipient'],
        amount=values['amount'],
        data=values.get('data')
    )
    
    # Retrieve the transaction details for P2P broadcasting
    with blockchain.lock:
        tx = blockchain.pending_transactions[-1]
        
    # Broadcast to peers
    p2p.broadcast({
        "type": "new_transaction",
        "transaction": tx.to_dict()
    })
    
    response = {
        "message": f"Transaction will be added to Block {next_block_index}",
        "transaction_id": tx.transaction_id,
        "transaction": tx.to_dict()
    }
    return jsonify(response), 201

@app.route('/mine', methods=['POST'])
def mine():
    """Mines a block from pending transactions using Proof of Work, then propagates it."""
    block = blockchain.mine_pending_transactions(miner_address=config.NODE_ID)
    if block is None:
        return jsonify({"message": "Mining aborted or block became stale due to chain updates"}), 409
        
    # Broadcast the mined block
    p2p.broadcast({
        "type": "new_block",
        "block": block.to_dict()
    })
    
    response = {
        "message": "New Block Mined Successfully",
        "index": block.index,
        "transactions": [tx.to_dict() for tx in block.transactions],
        "proof": block.proof,
        "previous_hash": block.previous_hash,
        "hash": block.hash
    }
    return jsonify(response), 200

@app.route('/peers', methods=['GET'])
def get_peers():
    """Retrieve details of all connected P2P peers."""
    with p2p.lock:
        peers_list = list(p2p.peers.values())
    response = {
        "peers": peers_list,
        "count": len(peers_list)
    }
    return jsonify(response), 200

@app.route('/status', methods=['GET'])
def get_status():
    """Check metadata status of this node."""
    with blockchain.lock:
        chain_len = len(blockchain.chain)
        pending_count = len(blockchain.pending_transactions)
        last_block = blockchain.get_last_block()
        
    response = {
        "node_id": config.NODE_ID,
        "is_bootstrap": config.IS_BOOTSTRAP,
        "http_port": config.HTTP_PORT,
        "p2p_port": config.P2P_PORT,
        "chain_length": chain_len,
        "pending_transactions_count": pending_count,
        "last_block_hash": last_block.hash
    }
    return jsonify(response), 200

@app.route('/pending', methods=['GET'])
def get_pending():
    """Retrieve the list of pending transactions in the mempool."""
    with blockchain.lock:
        pending_data = [tx.to_dict() for tx in blockchain.pending_transactions]
    return jsonify(pending_data), 200

@app.route('/contracts', methods=['GET'])
def get_contracts():
    """Retrieve all contracts and their computed states."""
    with blockchain.lock:
        contracts_state = ContractVM.compute_state(blockchain.chain)
    return jsonify(contracts_state), 200

@app.route('/contracts/<name>', methods=['GET'])
def get_contract(name):
    """Retrieve the computed state of a specific contract."""
    with blockchain.lock:
        contracts_state = ContractVM.compute_state(blockchain.chain)
    if name in contracts_state:
        return jsonify(contracts_state[name]), 200
    return jsonify({"message": f"Contract '{name}' not found"}), 404

if __name__ == '__main__':
    # Flask runs inside containers, listening on 0.0.0.0
    app.run(host='0.0.0.0', port=config.HTTP_PORT, debug=False, threaded=True)
