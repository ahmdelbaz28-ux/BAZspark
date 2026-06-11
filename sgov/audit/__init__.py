"""
SGL Audit & Trace Engine - Immutable Audit Trail System
"""

import json
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List
from ..models import ExecutionRequest, ExecutionTrace, PolicyDecision, ExecutionStatus
from ..exceptions import AuditException


class AuditEngine:
    """
    Audit & Trace Engine - Immutable Audit Trail System
    Every request generates structured, immutable logs with correlation
    """
    
    def __init__(self):
        self.audit_log: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self.storage_backend = None  # Could be configured to write to DB, file, etc.
    
    def initialize_trace(self, request: ExecutionRequest) -> ExecutionTrace:
        """
        Initialize an execution trace for a request
        
        Args:
            request: The execution request to trace
            
        Returns:
            ExecutionTrace object
        """
        trace = ExecutionTrace(request_id=request.request_id)
        
        # Log the initial request
        audit_entry = {
            "request_id": request.request_id,
            "timestamp": request.timestamp.isoformat(),
            "event_type": "REQUEST_RECEIVED",
            "user_id": request.user_id,
            "role": request.role.value,
            "risk_level": request.risk_level.value,
            "idempotency_key": request.idempotency_key,
            "payload_hash": hash(json.dumps(request.payload, sort_keys=True)),
            "metadata": request.metadata
        }
        
        self._write_audit_log(audit_entry)
        
        return trace
    
    def log_validation_result(self, request_id: str, is_valid: bool, error_message: str = ""):
        """
        Log the validation result
        
        Args:
            request_id: The request ID
            is_valid: Whether validation passed
            error_message: Error message if validation failed
        """
        audit_entry = {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "VALIDATION_RESULT",
            "is_valid": is_valid,
            "error_message": error_message
        }
        
        self._write_audit_log(audit_entry)
    
    def log_authorization_result(self, request_id: str, is_authorized: bool, role: str, action: str = ""):
        """
        Log the authorization result
        
        Args:
            request_id: The request ID
            is_authorized: Whether authorization passed
            role: The user role
            action: The action being authorized
        """
        audit_entry = {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "AUTHORIZATION_RESULT",
            "is_authorized": is_authorized,
            "role": role,
            "action": action
        }
        
        self._write_audit_log(audit_entry)
    
    def log_policy_decision(self, request_id: str, decision: PolicyDecision):
        """
        Log the policy decision
        
        Args:
            request_id: The request ID
            decision: The policy decision made
        """
        audit_entry = {
            "request_id": request_id,
            "timestamp": decision.decision_timestamp.isoformat(),
            "event_type": "POLICY_DECISION",
            "decision": decision.decision.value,
            "reason": decision.reason,
            "rules_applied": decision.rules_applied,
            "limits": {
                "max_execution_time_ms": decision.limits.max_execution_time_ms if decision.limits else 0,
                "max_memory_mb": decision.limits.max_memory_mb if decision.limits else 0,
                "max_tokens": decision.limits.max_tokens if decision.limits else 0
            } if decision.limits else None
        }
        
        self._write_audit_log(audit_entry)
    
    def log_layer_transition(self, request_id: str, from_layer: str, to_layer: str, latency_ms: float, details: Optional[Dict[str, Any]] = None):
        """
        Log the transition between layers
        
        Args:
            request_id: The request ID
            from_layer: The source layer
            to_layer: The destination layer
            latency_ms: Latency in milliseconds
            details: Additional details about the transition
        """
        audit_entry = {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "LAYER_TRANSITION",
            "from_layer": from_layer,
            "to_layer": to_layer,
            "latency_ms": latency_ms,
            "details": details or {}
        }
        
        self._write_audit_log(audit_entry)
    
    def log_execution_completion(self, trace: ExecutionTrace):
        """
        Log the completion of execution
        
        Args:
            trace: The execution trace with final status
        """
        audit_entry = {
            "request_id": trace.request_id,
            "timestamp": trace.end_time.isoformat() if trace.end_time else datetime.utcnow().isoformat(),
            "event_type": "EXECUTION_COMPLETED",
            "final_status": trace.final_status.value,
            "total_latency_ms": (trace.end_time - trace.start_time).total_seconds() * 1000 if trace.end_time else 0,
            "flow": [{"layer": step.layer, "latency_ms": step.latency_ms, "status": step.status} for step in trace.flow],
            "error_details": trace.error_details
        }
        
        self._write_audit_log(audit_entry)
    
    def log_security_event(self, request_id: str, event_type: str, severity: str, description: str, details: Optional[Dict[str, Any]] = None):
        """
        Log a security-related event
        
        Args:
            request_id: The request ID (if applicable)
            event_type: Type of security event
            severity: Severity level
            description: Event description
            details: Additional details
        """
        audit_entry = {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "SECURITY_EVENT",
            "security_event_type": event_type,
            "severity": severity,
            "description": description,
            "details": details or {}
        }
        
        self._write_audit_log(audit_entry)
    
    def get_audit_trail(self, request_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve the audit trail for a specific request
        
        Args:
            request_id: The request ID to retrieve audit trail for
            
        Returns:
            List of audit entries for the request
        """
        with self._lock:
            return [entry for entry in self.audit_log if entry.get("request_id") == request_id]
    
    def _write_audit_log(self, entry: Dict[str, Any]):
        """
        Write an audit entry to the log (thread-safe)
        
        Args:
            entry: The audit entry to write
        """
        with self._lock:
            # Append to in-memory log
            self.audit_log.append(entry)
            
            # If storage backend is configured, write there too
            if self.storage_backend:
                self.storage_backend.write(entry)
    
    def export_audit_log(self, request_ids: Optional[List[str]] = None) -> str:
        """
        Export audit log as JSON string
        
        Args:
            request_ids: Optional list of request IDs to filter by
            
        Returns:
            JSON string representation of the audit log
        """
        if request_ids:
            filtered_log = [entry for entry in self.audit_log if entry.get("request_id") in request_ids]
        else:
            filtered_log = self.audit_log
            
        return json.dumps(filtered_log, indent=2)