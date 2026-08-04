import hashlib
import hmac
import json
from datetime import datetime
from typing import Any, Dict, List


class MerkleNode:
    def __init__(self, data: Dict[str, Any], previous_hash: str = "GENESIS"):
        self.data = data
        self.previous_hash = previous_hash
        self.timestamp = datetime.utcnow().isoformat() + "Z"
        self.hash = self._calculate_hash()

    def _calculate_hash(self) -> str:
        """Calculates a deterministic SHA-256 hash of the node."""
        # Use a stable JSON serialization for hashing
        payload = json.dumps(
            {
                "data": self.data,
                "previous_hash": self.previous_hash,
                "timestamp": self.timestamp
            },
            sort_keys=True
        ).encode('utf-8')

        # In a real enterprise system, a secret key would be used for HMAC.
        # Here we use a generic secret for the sake of the structural implementation.
        secret = b"bazspark-audit-secret-key-12345"
        return hmac.new(secret, payload, hashlib.sha256).hexdigest()

class AuditMerkleTree:
    """
    Append-only Merkle tree structure for cryptographic audit trails.
    Compliant with the 14 UI coverage rules (specifically the requirement
    for verifiable, tamper-evident audit logs).
    """
    def __init__(self):
        self.nodes: List[MerkleNode] = []
        # Create Genesis block
        self._append_node({"event": "SYSTEM_STARTUP", "message": "Audit chain initialized"})

    def append_event(self, event_data: Dict[str, Any]) -> MerkleNode:
        """Appends a new event to the audit trail."""
        return self._append_node(event_data)

    def _append_node(self, data: Dict[str, Any]) -> MerkleNode:
        previous_hash = self.nodes[-1].hash if self.nodes else "GENESIS"
        new_node = MerkleNode(data, previous_hash)
        self.nodes.append(new_node)
        return new_node

    def verify_integrity(self) -> bool:
        """
        Verifies the cryptographic integrity of the entire chain.
        Returns True if intact, False if tampered.
        """
        if not self.nodes:
            return True

        for i in range(1, len(self.nodes)):
            current = self.nodes[i]
            previous = self.nodes[i-1]

            # Check linkage
            if current.previous_hash != previous.hash:
                return False

            # Check internal hash calculation
            if current.hash != current._calculate_hash():
                return False

        return True

    def get_chain(self) -> List[Dict[str, Any]]:
        """Returns the full chain for UI visualization."""
        return [
            {
                "hash": node.hash,
                "previous_hash": node.previous_hash,
                "timestamp": node.timestamp,
                "data": node.data
            }
            for node in self.nodes
        ]

# Global instance for the active session
_audit_tree = AuditMerkleTree()

def get_audit_tree() -> AuditMerkleTree:
    return _audit_tree
