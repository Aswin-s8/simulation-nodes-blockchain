import json
from typing import List, Dict, Any
from blockchain.block import Block
from blockchain.transaction import Transaction

class ContractVM:
    @staticmethod
    def compute_state(chain: List[Block]) -> Dict[str, Any]:
        """
        Processes the entire blockchain to compute the current state of all contracts.
        Returns a dict of contracts:
        {
            "contract_name": {
                "name": "contract_name",
                "type": "counter|token|guestbook",
                "owner": "deployer_address",
                "state": {...},
                "block_index": int,
                "timestamp": float,
                "tx_id": str,
                "history": [...]
            }
        }
        """
        contracts = {}
        
        # Iterate through the chain chronologically
        for block in chain:
            for tx in block.transactions:
                sender = tx.sender
                recipient = tx.recipient
                amount = tx.amount
                data = tx.data if isinstance(tx.data, dict) else {}
                
                # Check for deployment
                if recipient == "contract_deploy":
                    contract_name = data.get("contract_name")
                    contract_type = data.get("type")
                    params = data.get("params", {})
                    
                    if contract_name and contract_type:
                        # Avoid redeploying over an existing contract to prevent state hijacking
                        if contract_name not in contracts:
                            if contract_type == "counter":
                                initial_val = int(params.get("initial_value", 0))
                                state = {"count": initial_val}
                            elif contract_type == "token":
                                name = params.get("name", "CustomToken")
                                symbol = params.get("symbol", "CTK")
                                initial_supply = float(params.get("initial_supply", 1000.0))
                                state = {
                                    "name": name,
                                    "symbol": symbol,
                                    "balances": {sender: initial_supply}
                                }
                            elif contract_type == "guestbook":
                                state = {"messages": []}
                            else:
                                continue  # Unknown contract type
                                
                            contracts[contract_name] = {
                                "name": contract_name,
                                "type": contract_type,
                                "owner": sender,
                                "state": state,
                                "block_index": block.index,
                                "timestamp": tx.timestamp,
                                "tx_id": tx.transaction_id,
                                "history": []
                            }
                
                # Check for contract method calls
                elif recipient in contracts:
                    contract = contracts[recipient]
                    contract_type = contract["type"]
                    state = contract["state"]
                    method = data.get("method")
                    args = data.get("args", {})
                    
                    tx_record = {
                        "tx_id": tx.transaction_id,
                        "sender": sender,
                        "method": method,
                        "args": args,
                        "timestamp": tx.timestamp,
                        "block_index": block.index,
                        "success": False,
                        "error": None
                    }
                    
                    try:
                        if contract_type == "counter":
                            if method == "increment":
                                state["count"] += 1
                                tx_record["success"] = True
                            elif method == "decrement":
                                state["count"] -= 1
                                tx_record["success"] = True
                            else:
                                tx_record["error"] = f"Unknown method: {method}"
                                
                        elif contract_type == "token":
                            if method == "transfer":
                                to_addr = args.get("recipient")
                                transfer_amount = float(args.get("amount", 0))
                                if to_addr and transfer_amount > 0:
                                    sender_bal = state["balances"].get(sender, 0.0)
                                    if sender_bal >= transfer_amount:
                                        state["balances"][sender] = sender_bal - transfer_amount
                                        state["balances"][to_addr] = state["balances"].get(to_addr, 0.0) + transfer_amount
                                        tx_record["success"] = True
                                    else:
                                        tx_record["error"] = "Insufficient balance"
                                else:
                                    tx_record["error"] = "Invalid recipient or amount"
                            elif method == "mint":
                                mint_to = args.get("recipient", sender)
                                mint_amount = float(args.get("amount", 0))
                                # Only the owner can mint
                                if sender == contract["owner"]:
                                    if mint_amount > 0:
                                        state["balances"][mint_to] = state["balances"].get(mint_to, 0.0) + mint_amount
                                        tx_record["success"] = True
                                    else:
                                        tx_record["error"] = "Invalid mint amount"
                                else:
                                    tx_record["error"] = "Only contract owner can mint"
                            else:
                                tx_record["error"] = f"Unknown method: {method}"
                                
                        elif contract_type == "guestbook":
                            if method == "post":
                                msg_text = args.get("message")
                                if msg_text:
                                    state["messages"].append({
                                        "sender": sender,
                                        "message": msg_text,
                                        "timestamp": tx.timestamp,
                                        "block_index": block.index
                                    })
                                    tx_record["success"] = True
                                else:
                                    tx_record["error"] = "Empty message"
                            else:
                                tx_record["error"] = f"Unknown method: {method}"
                                
                    except Exception as e:
                        tx_record["error"] = str(e)
                        
                    contract["history"].append(tx_record)
                    
        return contracts
