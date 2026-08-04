from fastapi import APIRouter
from typing import Dict, Any, List
from fireai.audit.merkle import get_audit_tree

router = APIRouter(prefix="/audit", tags=["Audit"])

@router.get("/chain", response_model=List[Dict[str, Any]])
async def get_audit_chain():
    """
    Get the full Merkle Tree hash chain.
    Returns a cryptographically verifiable audit trail of system events.
    """
    tree = get_audit_tree()
    return tree.get_chain()

@router.get("/verify")
async def verify_audit_chain():
    """
    Verify the integrity of the audit hash chain.
    Returns True if intact, False if tampered.
    """
    tree = get_audit_tree()
    is_valid = tree.verify_integrity()
    return {
        "valid": is_valid,
        "message": "Audit chain is cryptographically valid." if is_valid else "WARNING: AUDIT CHAIN INTEGRITY COMPROMISED!"
    }
