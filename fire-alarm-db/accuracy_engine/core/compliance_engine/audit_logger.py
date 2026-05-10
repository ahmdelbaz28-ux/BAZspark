"""Audit logger for compliance verification traces."""

from datetime import datetime
from typing import List


class AuditLog:
    def __init__(self):
        self.entries = []

    def log(self, rule_id: str, status: str, details: dict, timestamp: str = None):
        self.entries.append({
            "rule_id": rule_id,
            "status": status,
            "details": details,
            "timestamp": timestamp or datetime.utcnow().isoformat()
        })

    def get_failures(self):
        return [e for e in self.entries if e["status"] == "FAIL"]

    def get_critical_failures(self):
        return [e for e in self.entries if e["status"] == "FAIL" and e.get("details", {}).get("severity") == "CRITICAL"]

    def summary(self):
        total = len(self.entries)
        passed = len([e for e in self.entries if e["status"] == "PASS"])
        failed = total - passed
        critical = len(self.get_critical_failures())
        return {
            "total_checks": total,
            "passed": passed,
            "failed": failed,
            "critical_failures": critical,
            "pass_rate": passed / total if total > 0 else 0
        }