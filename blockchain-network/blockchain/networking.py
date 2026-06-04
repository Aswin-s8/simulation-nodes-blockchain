import socket
import threading
import time
import struct
import json
import logging
from typing import List, Dict, Any, Optional
import config
from blockchain.transaction import Transaction
from blockchain.block import Block

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s')

class P2PNetwork:
    def __init__(self, blockchain):
        self.blockchain = blockchain
        self.node_id = config.NODE_ID
        self.p2p_port = config.P2P_PORT
        self.http_port = config.HTTP_PORT
        self.peers: Dict[str, Dict[str, Any]] = {}  # node_id -> {p2p_host, p2p_port, http_port}
        self.lock = threading.Lock()
        self.running = True

    def start(self):
        """Starts the P2P server and schedules background registration."""
        self.server_thread = threading.Thread(target=self.listen_to_peers, name="P2PServer", daemon=True)
        self.server_thread.start()
        
        # Connect to bootstrap node if configured and not itself
        if config.BOOTSTRAP_PEER and not config.IS_BOOTSTRAP:
            # BOOTSTRAP_PEER is "host:port"
            parts = config.BOOTSTRAP_PEER.split(':')
            bootstrap_host = parts[0]
            bootstrap_p2p_port = int(parts[1])
            
            # Start registration in a separate thread so it doesn't block startup
            threading.Thread(
                target=self.register_with_bootstrap, 
                args=(bootstrap_host, bootstrap_p2p_port), 
                name="BootstrapRegistrar",
                daemon=True
            ).start()

    def stop(self):
        """Stops background threads and listener."""
        self.running = False

    def listen_to_peers(self):
        """Listens on the P2P port for incoming TCP socket connections."""
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(('0.0.0.0', self.p2p_port))
        server_sock.listen(10)
        logging.info(f"P2P Node listening on port {self.p2p_port}")
        
        while self.running:
            try:
                # Set a timeout so we can exit the loop if self.running becomes False
                server_sock.settimeout(1.0)
                client_sock, addr = server_sock.accept()
                threading.Thread(
                    target=self.handle_client, 
                    args=(client_sock,), 
                    name=f"PeerHandler-{addr[0]}:{addr[1]}",
                    daemon=True
                ).start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logging.error(f"Error accepting connection: {e}")
        server_sock.close()

    def handle_client(self, sock: socket.socket):
        """Processes messages from a single peer connection."""
        try:
            msg = self.recv_message(sock)
            if not msg:
                return
            
            msg_type = msg.get("type")
            if msg_type == "register":
                self.handle_register(sock, msg)
            elif msg_type == "register_response":
                self.handle_register_response(msg)
            elif msg_type == "new_peer":
                self.handle_new_peer(msg)
            elif msg_type == "new_transaction":
                self.handle_new_transaction(msg)
            elif msg_type == "new_block":
                self.handle_new_block(sock, msg)
            elif msg_type == "get_chain":
                self.handle_get_chain(sock)
            elif msg_type == "chain_response":
                self.handle_chain_response(msg)
        except Exception as e:
            logging.error(f"Error handling P2P message: {e}", exc_info=True)
        finally:
            sock.close()

    # Message handlers
    def handle_register(self, sock: socket.socket, msg: dict):
        """Bootstrap node processes a registration request from a new node."""
        peer_id = msg["node_id"]
        peer_host = msg["p2p_host"]
        peer_p2p_port = msg["p2p_port"]
        peer_http_port = msg["http_port"]
        
        new_peer = {
            "node_id": peer_id,
            "p2p_host": peer_host,
            "p2p_port": peer_p2p_port,
            "http_port": peer_http_port
        }
        
        logging.info(f"Register request received from {peer_id} at {peer_host}:{peer_p2p_port}")
        
        with self.lock:
            # 1. Reply with current peers list (including bootstrap itself)
            current_peers = list(self.peers.values())
            # Add bootstrap node to the list sent to the peer
            bootstrap_peer = {
                "node_id": self.node_id,
                "p2p_host": "node1",  # Docker host name of bootstrap node
                "p2p_port": self.p2p_port,
                "http_port": self.http_port
            }
            # Avoid duplicate registration
            all_peers_to_send = [bootstrap_peer] + [p for p in current_peers if p["node_id"] != peer_id]
            
            response = {
                "type": "register_response",
                "peers": all_peers_to_send
            }
            self.send_message(sock, response)
            
            # 2. Add new peer to our list
            self.peers[peer_id] = new_peer
        
        # 3. Broadcast new peer announcement to all other peers
        announcement = {
            "type": "new_peer",
            "peer": new_peer
        }
        self.broadcast(announcement, exclude_peers=[peer_id])

    def handle_register_response(self, msg: dict):
        """Processes list of active network peers received from the bootstrap node."""
        peers_list = msg.get("peers", [])
        logging.info(f"Received register response with peers: {[p['node_id'] for p in peers_list]}")
        with self.lock:
            for peer in peers_list:
                peer_id = peer["node_id"]
                if peer_id != self.node_id:
                    self.peers[peer_id] = peer
                    logging.info(f"Discovered peer {peer_id} at {peer['p2p_host']}:{peer['p2p_port']}")

    def handle_new_peer(self, msg: dict):
        """Processes dynamic registration of a newly connected peer."""
        peer = msg["peer"]
        peer_id = peer["node_id"]
        if peer_id == self.node_id:
            return
            
        logging.info(f"New peer announced: {peer_id}")
        with self.lock:
            if peer_id not in self.peers:
                self.peers[peer_id] = peer
                logging.info(f"Registered new peer: {peer_id} ({peer['p2p_host']}:{peer['p2p_port']})")

    def handle_new_transaction(self, msg: dict):
        """Processes transaction propagated across P2P network."""
        tx_data = msg["transaction"]
        tx = Transaction.from_dict(tx_data)
        logging.info(f"Received P2P transaction: {tx.transaction_id[:8]}")
        added = self.blockchain.add_raw_transaction(tx)
        if added:
            # Re-broadcast transaction to other peers
            logging.info(f"Transaction {tx.transaction_id[:8]} added. Re-broadcasting.")
            self.broadcast(msg, exclude_peers=[msg.get("sender_node_id")])

    def handle_new_block(self, sock: socket.socket, msg: dict):
        """Processes new block propagated across P2P network."""
        block_data = msg["block"]
        block = Block.from_dict(block_data)
        logging.info(f"Received block #{block.index} (hash: {block.hash[:8]}) from peer")
        
        last_block = self.blockchain.get_last_block()
        
        if block.index > last_block.index + 1:
            logging.info(f"Block #{block.index} index is ahead of our last block #{last_block.index}. Requesting full chain.")
            # Request chain
            self.request_chain_from_socket(sock)
        elif block.index == last_block.index + 1:
            # Check if block is valid and append
            if self.blockchain.validate_block(block, last_block):
                with self.blockchain.lock:
                    self.blockchain.chain.append(block)
                    # Clean up pending transactions
                    mined_ids = {tx.transaction_id for tx in block.transactions}
                    self.blockchain.pending_transactions = [
                        tx for tx in self.blockchain.pending_transactions if tx.transaction_id not in mined_ids
                    ]
                    self.blockchain.save_chain()
                logging.info(f"Appended block #{block.index} to chain. Re-broadcasting block.")
                self.broadcast(msg, exclude_peers=[msg.get("sender_node_id")])
            else:
                logging.warning(f"Block #{block.index} validation failed.")

    def handle_get_chain(self, sock: socket.socket):
        """Sends the local chain sequence back to the requesting peer."""
        logging.info("Received request for full blockchain")
        with self.blockchain.lock:
            chain_data = [block.to_dict() for block in self.blockchain.chain]
        response = {
            "type": "chain_response",
            "chain": chain_data
        }
        self.send_message(sock, response)

    def handle_chain_response(self, msg: dict):
        """Processes the full chain from another peer and applies longest chain rule."""
        chain_data = msg.get("chain", [])
        logging.info(f"Received chain response of length {len(chain_data)}")
        try:
            new_blocks = [Block.from_dict(b) for b in chain_data]
            replaced = self.blockchain.replace_chain(new_blocks)
            if replaced:
                logging.info(f"Successfully synchronized chain. New height: {len(self.blockchain.chain)}")
                # Broadcast our new last block
                broadcast_msg = {
                    "type": "new_block",
                    "block": self.blockchain.get_last_block().to_dict(),
                    "sender_node_id": self.node_id
                }
                self.broadcast(broadcast_msg)
            else:
                logging.info("Chain synchronization: Received chain was not longer or not valid.")
        except Exception as e:
            logging.error(f"Error processing chain response: {e}")

    # Helper operations
    def register_with_bootstrap(self, host: str, port: int):
        """Registers this node with the bootstrap node."""
        retries = 15
        delay = 2.0
        logging.info(f"Attempting to register with bootstrap node {host}:{port}")
        for attempt in range(retries):
            if not self.running:
                break
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect((host, port))
                register_msg = {
                    "type": "register",
                    "node_id": self.node_id,
                    "p2p_host": self.node_id,  # In Docker compose, container name is host name
                    "p2p_port": self.p2p_port,
                    "http_port": self.http_port
                }
                self.send_message(sock, register_msg)
                
                # Wait for register_response
                response = self.recv_message(sock)
                if response and response.get("type") == "register_response":
                    self.handle_register_response(response)
                    sock.close()
                    logging.info("Successfully registered and configured peers list.")
                    break
                sock.close()
            except Exception as e:
                logging.warning(f"Failed to connect to bootstrap (attempt {attempt+1}/{retries}): {e}")
                time.sleep(delay)

    def request_chain_from_socket(self, sock: socket.socket):
        """Helper to send a GET_CHAIN command on an existing connection and receive the response."""
        try:
            req = {"type": "get_chain"}
            self.send_message(sock, req)
            resp = self.recv_message(sock)
            if resp and resp.get("type") == "chain_response":
                self.handle_chain_response(resp)
        except Exception as e:
            logging.error(f"Error requesting chain over socket: {e}")

    def broadcast(self, message: dict, exclude_peers: List[str] = None):
        """Sends a JSON message to all known peers."""
        if exclude_peers is None:
            exclude_peers = []
        # Inject sender node ID
        message["sender_node_id"] = self.node_id
        
        with self.lock:
            peers_snapshot = list(self.peers.values())
            
        for peer in peers_snapshot:
            peer_id = peer["node_id"]
            if peer_id in exclude_peers or peer_id == self.node_id:
                continue
            
            # Send message in a separate thread to prevent slow connections from blocking other broadcasts
            threading.Thread(
                target=self.send_message_to_address, 
                args=(peer["p2p_host"], peer["p2p_port"], message), 
                name=f"BroadcastTo-{peer_id}",
                daemon=True
            ).start()

    def send_message_to_address(self, host: str, port: int, message: dict):
        """Helper to open a socket, transmit a single message, and close the socket."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            sock.connect((host, port))
            self.send_message(sock, message)
            sock.close()
        except Exception as e:
            logging.debug(f"Could not send P2P message to {host}:{port}: {e}")

    # Sockets communication utilities
    def send_message(self, sock: socket.socket, data: dict):
        """Sends a length-prefixed JSON message."""
        try:
            payload = json.dumps(data).encode('utf-8')
            length = len(payload)
            sock.sendall(struct.pack('>I', length) + payload)
        except Exception as e:
            logging.error(f"Socket send error: {e}")

    def recv_message(self, sock: socket.socket) -> Optional[dict]:
        """Receives a length-prefixed JSON message."""
        try:
            raw_length = self.recvall(sock, 4)
            if not raw_length:
                return None
            length = struct.unpack('>I', raw_length)[0]
            raw_payload = self.recvall(sock, length)
            if not raw_payload:
                return None
            return json.loads(raw_payload.decode('utf-8'))
        except Exception as e:
            logging.error(f"Socket recv error: {e}")
            return None

    def recvall(self, sock: socket.socket, n: int) -> Optional[bytearray]:
        """Reads exactly n bytes from a socket, blocking if necessary."""
        data = bytearray()
        while len(data) < n:
            try:
                packet = sock.recv(n - len(data))
                if not packet:
                    return None
                data.extend(packet)
            except Exception:
                return None
        return data
