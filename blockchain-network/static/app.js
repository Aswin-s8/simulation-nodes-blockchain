// Configuration: Simulated Nodes in Network
const NODES = [
    { id: "node1", name: "Node 1 (Bootstrap)", port: 5001 },
    { id: "node2", name: "Node 2", port: 5002 },
    { id: "node3", name: "Node 3", port: 5003 },
    { id: "node4", name: "Node 4", port: 5004 },
    { id: "node5", name: "Node 5", port: 5005 }
];

// App State
let activeNodeIndex = 0; // default to Node 1
let activeWallet = "Alice_Wallet";
let nodeStatusCache = {}; // id -> { online: bool, chain_length: int }
let expandedBlocks = {}; // blockIndex -> bool
let activeTab = "transfer-tab";

// On page load
window.addEventListener("DOMContentLoaded", () => {
    initNodeGrid();
    adjustContractFormFields();
    updateWalletIdentity();
    
    // Initial data fetch
    pollNetworkStatus();
    refreshActiveNodeState();
    
    // Setup background polling loops
    setInterval(pollNetworkStatus, 3000); // Poll health of all nodes
    setInterval(refreshActiveNodeState, 2000); // Refresh active node details
});

// Create visual Node cards in the selector
function initNodeGrid() {
    const grid = document.getElementById("node-grid");
    grid.innerHTML = "";
    
    NODES.forEach((node, idx) => {
        const card = document.createElement("div");
        card.className = `node-card ${idx === activeNodeIndex ? 'active' : ''}`;
        card.id = `node-card-${node.id}`;
        card.onclick = () => selectActiveNode(idx);
        
        card.innerHTML = `
            <div class="node-card-header">
                <span class="node-card-title">${node.name}</span>
                <span class="pulse-ring" id="pulse-ring-${node.id}" style="background: #ef4444;"></span>
            </div>
            <div class="node-card-meta">
                <span>Port: ${node.port}</span>
                <span style="float: right;" id="height-${node.id}">Blocks: -</span>
            </div>
        `;
        grid.appendChild(card);
    });
}

// Switch current node focus
function selectActiveNode(idx) {
    activeNodeIndex = idx;
    
    // Update UI active card class
    NODES.forEach((node, i) => {
        const card = document.getElementById(`node-card-${node.id}`);
        if (card) {
            if (i === idx) {
                card.classList.add("active");
            } else {
                card.classList.remove("active");
            }
        }
    });
    
    showToast(`Switched explorer view to ${NODES[idx].name}`);
    refreshActiveNodeState();
}

// Get the base API url for the selected node
function getActiveNodeUrl() {
    return `http://localhost:${NODES[activeNodeIndex].port}`;
}

// Toast notification helper
function showToast(message, isError = false) {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.style.borderColor = isError ? "var(--danger)" : "var(--primary)";
    toast.classList.add("show");
    
    setTimeout(() => {
        toast.classList.remove("show");
    }, 3000);
}

// Poll health & block height for all nodes to update the top grid selector
async function pollNetworkStatus() {
    for (const node of NODES) {
        try {
            const res = await fetch(`http://localhost:${node.port}/status`);
            if (res.ok) {
                const data = await res.json();
                nodeStatusCache[node.id] = { online: true, chain_length: data.chain_length };
                
                // Update grid indicators
                document.getElementById(`pulse-ring-${node.id}`).style.background = "var(--success)";
                document.getElementById(`pulse-ring-${node.id}`).style.boxShadow = "0 0 0 0 var(--success-glow)";
                document.getElementById(`height-${node.id}`).textContent = `Blocks: ${data.chain_length}`;
            } else {
                throw new Error("offline");
            }
        } catch (e) {
            nodeStatusCache[node.id] = { online: false, chain_length: 0 };
            document.getElementById(`pulse-ring-${node.id}`).style.background = "var(--danger)";
            document.getElementById(`pulse-ring-${node.id}`).style.boxShadow = "none";
            document.getElementById(`height-${node.id}`).textContent = "Offline";
        }
    }
    
    // Update header active node status
    const activeNode = NODES[activeNodeIndex];
    const statusBadge = document.getElementById("active-node-badge");
    const activeStatus = nodeStatusCache[activeNode.id];
    
    if (activeStatus && activeStatus.online) {
        statusBadge.textContent = "ONLINE";
        statusBadge.className = "badge badge-online";
    } else {
        statusBadge.textContent = "OFFLINE";
        statusBadge.className = "badge badge-offline";
    }
}

// Fetch all states (chain, peers, mempool, contracts) for the currently focused node
async function refreshActiveNodeState() {
    const baseUrl = getActiveNodeUrl();
    const activeNodeId = NODES[activeNodeIndex].id;
    
    if (nodeStatusCache[activeNodeId] && !nodeStatusCache[activeNodeId].online) {
        // Active node is offline, render blank states
        renderBlankStates();
        return;
    }
    
    try {
        // 1. Fetch Node Status Info
        const statusRes = await fetch(`${baseUrl}/status`);
        if (!statusRes.ok) throw new Error();
        const statusData = await statusRes.json();
        
        document.getElementById("val-node-id").textContent = statusData.node_id;
        document.getElementById("val-http-port").textContent = statusData.http_port;
        document.getElementById("val-p2p-port").textContent = statusData.p2p_port;
        document.getElementById("val-node-role").textContent = statusData.is_bootstrap ? "Bootstrap Node" : "Standard Node";
        
        // 2. Fetch P2P Peers
        const peersRes = await fetch(`${baseUrl}/peers`);
        const peersData = await peersRes.json();
        renderPeersList(peersData.peers);
        
        // 3. Fetch Mempool (Pending Tx)
        const pendingRes = await fetch(`${baseUrl}/pending`);
        const pendingData = await pendingRes.json();
        renderPendingList(pendingData);
        
        // 4. Fetch Blockchain Explorer
        const chainRes = await fetch(`${baseUrl}/chain`);
        const chainData = await chainRes.json();
        renderBlockchainExplorer(chainData.chain);
        
        // 5. Fetch Smart Contracts State
        const contractsRes = await fetch(`${baseUrl}/contracts`);
        const contractsData = await contractsRes.json();
        renderContractsDashboard(contractsData);
        
    } catch (err) {
        console.error("Error updating active node dashboard state", err);
    }
}

function renderBlankStates() {
    document.getElementById("val-node-id").textContent = "OFFLINE";
    document.getElementById("val-http-port").textContent = "-";
    document.getElementById("val-p2p-port").textContent = "-";
    document.getElementById("val-node-role").textContent = "-";
    document.getElementById("peers-count").textContent = "0";
    document.getElementById("peers-chips").innerHTML = `<div style="color:var(--danger); font-size:0.8rem;">Cannot connect to node API.</div>`;
    document.getElementById("pending-list").innerHTML = `<div class="empty-state">Node is unreachable.</div>`;
    document.getElementById("mempool-count").textContent = "0";
    document.getElementById("blockchain-timeline").innerHTML = `<div class="empty-state">No connection.</div>`;
    document.getElementById("explorer-block-height").textContent = "Height: 0";
    document.getElementById("contracts-grid").innerHTML = `<div class="empty-state">No connection.</div>`;
}

// Renders P2P network peers visual chips
function renderPeersList(peers) {
    document.getElementById("peers-count").textContent = peers.length;
    const container = document.getElementById("peers-chips");
    
    if (peers.length === 0) {
        container.innerHTML = `<span style="font-size:0.8rem; color:var(--text-secondary);">No active P2P peers connected.</span>`;
        return;
    }
    
    container.innerHTML = "";
    peers.forEach(peer => {
        const chip = document.createElement("span");
        chip.className = "peer-chip";
        chip.textContent = `${peer.node_id} (${peer.p2p_host}:${peer.p2p_port})`;
        container.appendChild(chip);
    });
}

// Renders the mempool pending transaction queue
function renderPendingList(pendingTxs) {
    document.getElementById("mempool-count").textContent = pendingTxs.length;
    const container = document.getElementById("pending-list");
    
    if (pendingTxs.length === 0) {
        container.innerHTML = `<div class="empty-state">No pending transactions in mempool.</div>`;
        return;
    }
    
    container.innerHTML = "";
    pendingTxs.forEach(tx => {
        const div = document.createElement("div");
        div.className = "tx-item";
        
        let customDataBadge = "";
        if (tx.data && Object.keys(tx.data).length > 0) {
            customDataBadge = `<div class="tx-data-badge">Payload: ${JSON.stringify(tx.data)}</div>`;
        }
        
        div.innerHTML = `
            <div class="tx-header">
                <span class="tx-id font-mono">ID: ${tx.transaction_id.slice(0, 8)}...</span>
                <span class="tx-amount">${tx.amount} NATIVE</span>
            </div>
            <div class="tx-parties">
                <span>From: <strong class="font-mono">${tx.sender.slice(0, 12)}</strong></span>
                <span>To: <strong class="font-mono">${tx.recipient.slice(0, 12)}</strong></span>
            </div>
            ${customDataBadge}
        `;
        container.appendChild(div);
    });
}

// Renders blocks & transactions list
function renderBlockchainExplorer(chain) {
    document.getElementById("explorer-block-height").textContent = `Height: ${chain.length}`;
    const container = document.getElementById("blockchain-timeline");
    container.innerHTML = "";
    
    // Display in reverse chronological order (newest blocks first)
    for (let i = chain.length - 1; i >= 0; i--) {
        const block = chain[i];
        const card = document.createElement("div");
        card.className = "block-card";
        
        const isExpanded = expandedBlocks[block.index] === true;
        
        let txRows = "";
        if (block.transactions.length === 0) {
            txRows = `<div class="empty-state" style="padding:0.75rem;">No transactions in this block.</div>`;
        } else {
            block.transactions.forEach(tx => {
                let payloadMarkup = "";
                if (tx.data && Object.keys(tx.data).length > 0) {
                    payloadMarkup = `<div class="tx-data-badge" style="background:rgba(99,102,241,0.08);">Payload: ${JSON.stringify(tx.data)}</div>`;
                }
                txRows += `
                    <div class="tx-item" style="background:rgba(0,0,0,0.15); margin-bottom:0.5rem; border-color:rgba(255,255,255,0.03);">
                        <div class="tx-header">
                            <span class="tx-id font-mono">ID: ${tx.transaction_id.slice(0, 8)}...</span>
                            <span class="tx-amount" style="color:var(--accent);">${tx.amount} NATIVE</span>
                        </div>
                        <div class="tx-parties">
                            <span>From: <span class="font-mono" style="color:#e2e8f0;">${tx.sender}</span></span>
                            <span>To: <span class="font-mono" style="color:#e2e8f0;">${tx.recipient}</span></span>
                        </div>
                        ${payloadMarkup}
                    </div>
                `;
            });
        }
        
        const dateStr = new Date(block.timestamp * 1000).toLocaleTimeString();
        
        card.innerHTML = `
            <div class="block-card-header" onclick="toggleBlockExpansion(${block.index})">
                <div class="block-title">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="2.5"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/></svg>
                    Block #${block.index}
                    <span style="font-size:0.75rem; font-weight:400; color:var(--text-secondary); margin-left:0.5rem;">(${block.transactions.length} txs, Solved Proof: ${block.proof})</span>
                </div>
                <div style="display:flex; align-items:center; gap:1rem;">
                    <span class="block-hash font-mono">Hash: ${block.hash.slice(0, 8)}...</span>
                    <span style="font-size:0.75rem; color:var(--text-secondary);">${dateStr}</span>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="transform:${isExpanded ? 'rotate(180deg)' : 'none'}; transition: transform 0.2s;"><polyline points="6 9 12 15 18 9"/></svg>
                </div>
            </div>
            
            <div class="block-details ${isExpanded ? 'show' : ''}">
                <div class="meta-grid" style="margin-bottom:0.5rem;">
                    <div class="meta-item">
                        <span class="meta-label">Previous Hash</span>
                        <span class="meta-value font-mono">${block.previous_hash.slice(0, 16)}...</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">Full Block Hash</span>
                        <span class="meta-value font-mono">${block.hash.slice(0, 16)}...</span>
                    </div>
                </div>
                <div>
                    <h4 style="margin-top:0.5rem; font-size:0.8rem;">Block Transactions Ledger</h4>
                    <div style="margin-top:0.5rem;">
                        ${txRows}
                    </div>
                </div>
            </div>
        `;
        container.appendChild(card);
    }
}

function toggleBlockExpansion(index) {
    expandedBlocks[index] = !expandedBlocks[index];
    // Re-render dashboard explorer instantly (state is preserved)
    refreshActiveNodeState();
}

// Renders Smart Contracts list and dynamic UI control widgets
function renderContractsDashboard(contracts) {
    const container = document.getElementById("contracts-grid");
    const contractNames = Object.keys(contracts);
    
    if (contractNames.length === 0) {
        container.innerHTML = `<div class="empty-state">No active smart contracts deployed yet. Deploy one to start interacting!</div>`;
        return;
    }
    
    container.innerHTML = "";
    
    contractNames.forEach(name => {
        const contract = contracts[name];
        const card = document.createElement("div");
        card.className = `contract-card contract-${contract.type}`;
        
        let stateMarkup = "";
        let actionsMarkup = "";
        
        // Renders visual states & execution forms depending on contract types
        if (contract.type === "counter") {
            stateMarkup = `
                <div class="contract-state-box">
                    <div class="meta-label" style="text-align:center;">Counter Value</div>
                    <div class="counter-value">${contract.state.count}</div>
                </div>
            `;
            actionsMarkup = `
                <div class="contract-actions">
                    <span class="meta-label">Execute Methods</span>
                    <div class="action-row-inline">
                        <button class="btn btn-primary btn-sm btn-block" onclick="callContractMethod('${name}', 'increment')">Increment (+1)</button>
                        <button class="btn btn-secondary btn-sm btn-block" onclick="callContractMethod('${name}', 'decrement')">Decrement (-1)</button>
                    </div>
                </div>
            `;
        } else if (contract.type === "token") {
            let balancesRows = "";
            const balances = contract.state.balances;
            Object.keys(balances).forEach(wallet => {
                balancesRows += `
                    <div class="balance-item">
                        <span class="font-mono">${wallet}</span>
                        <strong>${balances[wallet]} ${contract.state.symbol}</strong>
                    </div>
                `;
            });
            
            stateMarkup = `
                <div class="contract-state-box">
                    <div class="meta-label" style="margin-bottom:0.4rem;">Token Balances (${contract.state.name} - ${contract.state.symbol})</div>
                    <div class="token-balances-list">
                        ${balancesRows || '<span style="font-size:0.8rem; color:var(--text-secondary)">No balances found.</span>'}
                    </div>
                </div>
            `;
            
            // Check if current active identity is contract owner to enable Mint
            const isOwner = activeWallet === contract.owner;
            const mintButtonState = isOwner ? "" : "disabled";
            const mintTitle = isOwner ? "Mint Tokens (Owner only)" : "Mint Tokens (Requires owner wallet)";
            
            actionsMarkup = `
                <div class="contract-actions">
                    <span class="meta-label">Token Transfer</span>
                    <div class="action-row-inline">
                        <input type="text" id="arg-transfer-to-${name}" class="form-control btn-sm" style="flex:2;" placeholder="To Address">
                        <input type="number" id="arg-transfer-amt-${name}" class="form-control btn-sm" style="flex:1;" placeholder="Amt" min="1">
                        <button class="btn btn-primary btn-sm" onclick="triggerTokenTransfer('${name}')">Send</button>
                    </div>
                    
                    <div style="border-top:1px solid rgba(255,255,255,0.04); padding-top:0.5rem; margin-top:0.25rem;">
                        <span class="meta-label" title="${mintTitle}">${isOwner ? '👑 Mint Tokens' : '🔒 Mint Tokens (Owner Only)'}</span>
                        <div class="action-row-inline">
                            <input type="text" id="arg-mint-to-${name}" class="form-control btn-sm" style="flex:2;" placeholder="Recipient" value="${activeWallet}" ${mintButtonState}>
                            <input type="number" id="arg-mint-amt-${name}" class="form-control btn-sm" style="flex:1;" placeholder="Amount" min="1" ${mintButtonState}>
                            <button class="btn btn-secondary btn-sm" onclick="triggerTokenMint('${name}')" ${mintButtonState}>Mint</button>
                        </div>
                    </div>
                </div>
            `;
        } else if (contract.type === "guestbook") {
            let messagesList = "";
            const messages = contract.state.messages || [];
            
            messages.forEach(msg => {
                const dateStr = new Date(msg.timestamp * 1000).toLocaleTimeString();
                messagesList += `
                    <div class="guestbook-item">
                        <div class="guestbook-meta">
                            <span class="font-mono text-secondary">${msg.sender.slice(0, 16)}</span>
                            <span>${dateStr}</span>
                        </div>
                        <div style="font-size:0.85rem; color:#fff; word-break:break-all;">${msg.message}</div>
                    </div>
                `;
            });
            
            stateMarkup = `
                <div class="contract-state-box">
                    <div class="meta-label" style="margin-bottom:0.4rem;">Bulletin Board Messages</div>
                    <div class="guestbook-list">
                        ${messagesList || '<div style="font-size:0.8rem; color:var(--text-secondary); text-align:center; padding:0.5rem;">No posts yet. Be the first!</div>'}
                    </div>
                </div>
            `;
            
            actionsMarkup = `
                <div class="contract-actions">
                    <span class="meta-label">Post Public Message</span>
                    <div class="action-row-inline">
                        <input type="text" id="arg-msg-text-${name}" class="form-control btn-sm" style="flex:3;" placeholder="Write message details...">
                        <button class="btn btn-primary btn-sm" onclick="triggerGuestbookPost('${name}')">Post</button>
                    </div>
                </div>
            `;
        }
        
        card.innerHTML = `
            <div class="contract-header">
                <div class="contract-info">
                    <h4>${name}</h4>
                    <span class="contract-owner">Owner: <span class="font-mono">${contract.owner.slice(0, 16)}...</span></span>
                </div>
                <span class="badge" style="text-transform: uppercase;">${contract.type}</span>
            </div>
            
            ${stateMarkup}
            ${actionsMarkup}
        `;
        
        container.appendChild(card);
    });
}

// Setup identity selection helper
function updateWalletIdentity() {
    activeWallet = document.getElementById("wallet-select").value;
    // Instantly refresh cards if we change identities (handles dynamic enabled/disabled buttons)
    refreshActiveNodeState();
}

// Forms tabs switcher helper
function switchFormTab(tabId) {
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    
    document.getElementById(tabId).classList.add("active");
    // Add active to the clicked button
    const btns = document.querySelectorAll(".tab-btn");
    if (tabId === "transfer-tab") btns[0].classList.add("active");
    if (tabId === "contract-tab") btns[1].classList.add("active");
    
    activeTab = tabId;
}

// Adjust form inputs display dynamically based on contract type selected
function adjustContractFormFields() {
    const type = document.getElementById("contract-type").value;
    
    const show = (id) => document.getElementById(id).style.display = "block";
    const hide = (id) => document.getElementById(id).style.display = "none";
    
    if (type === "counter") {
        show("field-initial-val");
        hide("field-token-name");
        hide("field-token-symbol");
        hide("field-token-supply");
    } else if (type === "token") {
        hide("field-initial-val");
        show("field-token-name");
        show("field-token-symbol");
        show("field-token-supply");
    } else if (type === "guestbook") {
        hide("field-initial-val");
        hide("field-token-name");
        hide("field-token-symbol");
        hide("field-token-supply");
    }
}

// Form Submission: Regular Native Coin Transaction
async function submitTransaction(event) {
    event.preventDefault();
    const recipient = document.getElementById("tx-recipient").value.trim();
    const amount = parseFloat(document.getElementById("tx-amount").value);
    const baseUrl = getActiveNodeUrl();
    
    if (!recipient) {
        showToast("Invalid recipient address", true);
        return;
    }
    
    try {
        const response = await fetch(`${baseUrl}/transaction`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                sender: activeWallet,
                recipient: recipient,
                amount: amount
            })
        });
        
        const data = await response.json();
        if (response.ok) {
            showToast("Transaction broadcast successfully!");
            document.getElementById("tx-recipient").value = "";
            refreshActiveNodeState();
        } else {
            showToast(data.message || "Failed to broadcast transaction", true);
        }
    } catch (e) {
        showToast("Error communicating with Node API", true);
    }
}

// Form Submission: Deploy Smart Contract
async function deployContract(event) {
    event.preventDefault();
    const contractId = document.getElementById("contract-name").value.trim();
    const type = document.getElementById("contract-type").value;
    const baseUrl = getActiveNodeUrl();
    
    if (!contractId || !/^[a-zA-Z0-9_]+$/.test(contractId)) {
        showToast("Contract ID must be alphanumeric/underscores only.", true);
        return;
    }
    
    // Construct contract creation params payload
    let params = {};
    if (type === "counter") {
        params.initial_value = parseInt(document.getElementById("param-initial-val").value) || 0;
    } else if (type === "token") {
        params.name = document.getElementById("param-token-name").value || "CustomToken";
        params.symbol = document.getElementById("param-token-symbol").value || "CTK";
        params.initial_supply = parseFloat(document.getElementById("param-token-supply").value) || 1000.0;
    }
    
    try {
        const response = await fetch(`${baseUrl}/transaction`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                sender: activeWallet,
                recipient: "contract_deploy",
                amount: 0,
                data: {
                    contract_name: contractId,
                    type: type,
                    params: params
                }
            })
        });
        
        const data = await response.json();
        if (response.ok) {
            showToast(`Contract '${contractId}' deployment pending! Mine a block to compile.`);
            document.getElementById("contract-name").value = "";
            switchFormTab("transfer-tab");
            refreshActiveNodeState();
        } else {
            showToast(data.message || "Failed to deploy contract", true);
        }
    } catch (e) {
        showToast("Error communicating with Node API", true);
    }
}

// Triggers mining puzzle solving on active node
async function mineBlock() {
    const baseUrl = getActiveNodeUrl();
    showToast("Starting Proof of Work puzzle mining...");
    
    try {
        const response = await fetch(`${baseUrl}/mine`, {
            method: "POST"
        });
        
        const data = await response.json();
        if (response.ok) {
            showToast(`Success! Block #${data.index} mined & synchronized.`);
            refreshActiveNodeState();
            pollNetworkStatus(); // Sync block heights grid
        } else {
            showToast(data.message || "Mining failed.", true);
        }
    } catch (e) {
        showToast("Error communicating with Node API", true);
    }
}

// Contract Method Invocation Engine
async function callContractMethod(contractName, method, args = {}) {
    const baseUrl = getActiveNodeUrl();
    
    try {
        const response = await fetch(`${baseUrl}/transaction`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                sender: activeWallet,
                recipient: contractName,
                amount: 0,
                data: {
                    method: method,
                    args: args
                }
            })
        });
        
        const data = await response.json();
        if (response.ok) {
            showToast(`Call to '${contractName}.${method}' broadcast! Mine a block to apply changes.`);
            refreshActiveNodeState();
        } else {
            showToast(data.message || "Contract call failed", true);
        }
    } catch (e) {
        showToast("Error communicating with Node API", true);
    }
}

// Call wrapper for Custom Token Transfer
function triggerTokenTransfer(contractName) {
    const to = document.getElementById(`arg-transfer-to-${contractName}`).value.trim();
    const amount = parseFloat(document.getElementById(`arg-transfer-amt-${contractName}`).value);
    
    if (!to || isNaN(amount) || amount <= 0) {
        showToast("Invalid token transfer args", true);
        return;
    }
    
    callContractMethod(contractName, "transfer", { recipient: to, amount: amount });
    // Reset inputs
    document.getElementById(`arg-transfer-to-${contractName}`).value = "";
    document.getElementById(`arg-transfer-amt-${contractName}`).value = "";
}

// Call wrapper for Custom Token Minting
function triggerTokenMint(contractName) {
    const to = document.getElementById(`arg-mint-to-${contractName}`).value.trim();
    const amount = parseFloat(document.getElementById(`arg-mint-amt-${contractName}`).value);
    
    if (!to || isNaN(amount) || amount <= 0) {
        showToast("Invalid token mint args", true);
        return;
    }
    
    callContractMethod(contractName, "mint", { recipient: to, amount: amount });
    // Reset inputs
    document.getElementById(`arg-mint-amt-${contractName}`).value = "";
}

// Call wrapper for posting a guestbook message
function triggerGuestbookPost(contractName) {
    const msg = document.getElementById(`arg-msg-text-${contractName}`).value.trim();
    
    if (!msg) {
        showToast("Message text cannot be empty", true);
        return;
    }
    
    callContractMethod(contractName, "post", { message: msg });
    // Reset input
    document.getElementById(`arg-msg-text-${contractName}`).value = "";
}
