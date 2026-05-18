"""
audit_store.py – Tamper-Evident Audit Log for NFPA 72 Compliance
=========================================================
Immutable audit log with hash chain verification.
Designed for legal/production use.

nfpa_version: NFPA 72-2022
"""

import json
import sqlite3
import hmac
import hashlib
import datetime
import os
from typing import List, Dict, Optional, Any

# ============================================================================
# CONFIGURATION
# ============================================================================

NFPA_VERSION = "NFPA 72-2022"

# Default HMAC key - use environment variable in production
_DEFAULT_HMAC_KEY = "dev-key-change-in-production"


def _get_hmac_key() -> str:
    """Get HMAC key from environment or return default.
    
    Returns:
        The HMAC key for signing events.
    """
    return os.environ.get("AUDIT_HMAC_KEY", _DEFAULT_HMAC_KEY)


# Database path - can be overridden via environment
DATABASE_PATH = os.environ.get("AUDIT_DB_PATH", os.path.join(os.path.dirname(__file__), "audit_store.db"))


# ============================================================================
# DATABASE SETUP
# ============================================================================

# Track whether database has been initialized
_db_initialized = False


def _init_database() -> None:
    """Initialize database with audit_log table and triggers."""
    global _db_initialized
    if _db_initialized:
        return
    # Ensure parent directory exists
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir and not os.path.isdir(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Create table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            room_id TEXT,
            details TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            current_hash TEXT NOT NULL,
            signature TEXT
        )
    """)
    
    # Create trigger to prevent UPDATE
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS prevent_update
        BEFORE UPDATE ON audit_log
        FOR EACH ROW
        BEGIN
            SELECT RAISE(ABORT, 'UPDATE operations are forbidden on audit log');
        END
    """)
    
    # Create trigger to prevent DELETE
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS prevent_delete
        BEFORE DELETE ON audit_log
        FOR EACH ROW
        BEGIN
            SELECT RAISE(ABORT, 'DELETE operations are forbidden on audit log');
        END
    """)
    
    conn.commit()
    conn.close()
    _db_initialized = True


def _get_connection() -> sqlite3.Connection:
    """Get database connection (initializes on first call)."""
    _init_database()
    return sqlite3.connect(DATABASE_PATH)


# ============================================================================
# HASH CHAIN LOGIC
# ============================================================================

def _compute_hash(timestamp: str, event_type: str, room_id: str, 
                 details_json: str, previous_hash: str) -> str:
    """Compute SHA-256 hash for the event."""
    payload = f"{timestamp}|{event_type}|{room_id}|{details_json}|{previous_hash}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _compute_signature(current_hash: str) -> str:
    """Compute HMAC-SHA256 signature using unified key."""
    key = _get_hmac_key()
    return hmac.new(
        key.encode(),
        current_hash.encode(),
        hashlib.sha256
    ).hexdigest()


def _get_last_hash() -> str:
    """Get the current_hash of the last event, or GENESIS if empty."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT current_hash FROM audit_log ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "GENESIS"


# ============================================================================
# PUBLIC API
# ============================================================================

def add_event(event_type: str, room_id: str, details_dict: Dict[str, Any]) -> str:
    """
    Add a new audit event to the chain.
    
    Args:
        event_type: Type of event (e.g., "ROOM_ANALYSIS", "DETECTOR_PLACEMENT")
        room_id: Room identifier
        details_dict: Event details as dictionary
    
    Returns:
        current_hash of the added event
    """
    # Validate details
    if not isinstance(details_dict, dict):
        raise ValueError("details_dict must be a dictionary")
    
    # Generate timestamp
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
    
    # Get previous hash
    previous_hash = _get_last_hash()
    
    # Serialize details
    details_json = json.dumps(details_dict, sort_keys=True)
    
    # Compute current hash
    current_hash = _compute_hash(timestamp, event_type, room_id, details_json, previous_hash)
    
    # Compute signature
    signature = _compute_signature(current_hash)
    
    # Insert event
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_log (timestamp, event_type, room_id, details, previous_hash, current_hash, signature)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (timestamp, event_type, room_id, details_json, previous_hash, current_hash, signature))
    conn.commit()
    conn.close()
    
    return current_hash


def verify_chain() -> tuple[bool, Optional[Dict[str, Any]]]:
    """
    Verify the integrity of the entire hash chain AND HMAC signature.
    
    Returns:
        (is_valid, error_details) tuple
        - is_valid: True if chain AND signatures are intact, False if tampered
        - error_details: Details of the tampered event if any
    """
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_log ORDER BY id")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return True, None
    
    # Get HMAC key
    key = _get_hmac_key()
    
    # Check each event
    for i, row in enumerate(rows):
        event_id, timestamp, event_type, room_id, details_json, previous_hash, current_hash, signature = row
        
        # 1. Verify hash
        expected_hash = _compute_hash(timestamp, event_type, room_id, details_json, previous_hash)
        
        if expected_hash != current_hash:
            return False, {
                "event_id": event_id,
                "event_type": event_type,
                "room_id": room_id,
                "reason": "Hash mismatch - data tampered",
                "expected": expected_hash,
                "actual": current_hash
            }
        
        # 2. Verify signature
        if not signature or signature.strip() == "":
            return False, {
                "event_id": event_id,
                "event_type": event_type,
                "room_id": room_id,
                "reason": "Missing HMAC signature",
            }
        
        # Compute expected signature
        expected_signature = hmac.new(
            key.encode(),
            expected_hash.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if expected_signature != signature:
            return False, {
                "event_id": event_id,
                "event_type": event_type,
                "room_id": room_id,
                "reason": "HMAC signature mismatch - key invalid or event tampered",
                "expected": expected_signature,
                "actual": signature
            }
    
    return True, None


def get_events() -> List[Dict[str, Any]]:
    """
    Get all events as a list of dictionaries (read-only).
    
    Returns:
        List of event dictionaries
    """
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_log ORDER BY id")
    rows = cursor.fetchall()
    conn.close()
    
    events = []
    for row in rows:
        event_id, timestamp, event_type, room_id, details_json, previous_hash, current_hash, signature = row
        events.append({
            "id": event_id,
            "timestamp": timestamp,
            "event_type": event_type,
            "room_id": room_id,
            "details": json.loads(details_json),
            "previous_hash": previous_hash,
            "current_hash": current_hash,
            "signature": signature
        })
    
    return events


# ============================================================================
# FACADE CLASS — public API surface
# ============================================================================

class AuditStore:
    """Facade class for tamper-evident audit log operations.

    Delegates to the module-level functions so that callers can use
    either the functional API (``add_event()``) or the class-based
    API (``AuditStore.add_event()``).
    """

    @staticmethod
    def add_event(event_type: str, room_id: str, details_dict: Dict[str, Any]) -> str:
        """Add a new audit event to the hash chain."""
        return add_event(event_type, room_id, details_dict)

    @staticmethod
    def verify_chain() -> tuple:
        """Verify integrity of the entire hash chain and HMAC signatures."""
        return verify_chain()

    @staticmethod
    def get_events() -> List[Dict[str, Any]]:
        """Return all events as a list of dictionaries (read-only)."""
        return get_events()


# ============================================================================
# INITIALIZATION
# ============================================================================

# Database is initialized lazily on first connection (not at import time).
# This prevents import-time failures when the DB path is not writable.
# _init_database() is called by _get_connection() on first use.