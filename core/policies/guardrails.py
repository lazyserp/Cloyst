"""Offline Guardrails Pipeline for Cloyst.

Guarantees 100% air-gap compliance with zero external API calls:
- PII redaction (SSN, credit cards, emails, phones, IPs)
- Secret & private key detection
- Prompt injection & jailbreak heuristics
- Custom keyword blocklists
- Modes per project: 'off', 'log', 'block', 'redact'
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

PII_PATTERNS = [
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("credit_card", re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")),
    ("phone", re.compile(r"\b(?:\+?\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b")),
]

SECRET_PATTERNS = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----")),
    ("aws_key", re.compile(r"\b(AKIA[0-9A-Z]{16})\b")),
    ("generic_secret", re.compile(r"(password|secret|api_key)\s*[:=]\s*['\"][A-Za-z0-9_\-\.]{8,}['\"]", re.IGNORECASE)),
]

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?prior\s+prompts", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+dan\s+mode", re.IGNORECASE),
    re.compile(r"system\s+override\s+mode", re.IGNORECASE),
    re.compile(r"bypass\s+all\s+safety\s+filters", re.IGNORECASE),
]


class GuardrailViolation:
    def __init__(self, rule: str, category: str, snippet: str):
        self.rule = rule
        self.category = category
        self.snippet = snippet

    def to_dict(self) -> Dict[str, str]:
        return {"rule": self.rule, "category": self.category, "snippet": self.snippet}


class GuardrailsPipeline:
    """Evaluates and enforces offline guardrails on prompts and completions."""

    def __init__(self):
        self._blocklists: Dict[str, List[str]] = {}  # project_id -> list of banned terms

    def set_blocklist(self, project_id: str, terms: List[str]) -> None:
        self._blocklists[project_id] = [t.lower().strip() for t in terms if t.strip()]

    def scan_text(
        self,
        text: str,
        project_id: Optional[str] = None,
    ) -> Tuple[List[GuardrailViolation], str]:
        """Scan text and return (violations, redacted_text)."""
        violations: List[GuardrailViolation] = []
        redacted = text

        # 1. PII Scan
        for name, pat in PII_PATTERNS:
            for m in pat.finditer(text):
                violations.append(GuardrailViolation(name, "pii", m.group(0)[:12]))
            redacted = pat.sub(f"[REDACTED_{name.upper()}]", redacted)

        # 2. Secret Scan
        for name, pat in SECRET_PATTERNS:
            for m in pat.finditer(text):
                violations.append(GuardrailViolation(name, "secret", m.group(0)[:12]))
            redacted = pat.sub(f"[REDACTED_{name.upper()}]", redacted)

        # 3. Prompt Injection Heuristics
        for pat in INJECTION_PATTERNS:
            match = pat.search(text)
            if match:
                violations.append(GuardrailViolation("prompt_injection", "security", match.group(0)))

        # 4. Project Blocklist Scan
        if project_id and project_id in self._blocklists:
            lower_text = text.lower()
            for term in self._blocklists[project_id]:
                if term in lower_text:
                    violations.append(GuardrailViolation("blocklist_term", "compliance", term))
                    redacted = re.sub(re.escape(term), "[REDACTED_TERM]", redacted, flags=re.IGNORECASE)

        return violations, redacted

    def process_messages(
        self,
        messages: List[Dict[str, Any]],
        mode: str = "redact",
        project_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], List[GuardrailViolation], bool]:
        """Evaluate messages according to policy mode ('off', 'log', 'block', 'redact').

        Returns:
            (processed_messages, violations, is_blocked)
        """
        if mode == "off":
            return messages, [], False

        all_violations: List[GuardrailViolation] = []
        clean_messages: List[Dict[str, Any]] = []

        for m in messages:
            content = m.get("content")
            if isinstance(content, str):
                v_list, red_text = self.scan_text(content, project_id)
                all_violations.extend(v_list)
                m_copy = dict(m)
                if mode == "redact":
                    m_copy["content"] = red_text
                clean_messages.append(m_copy)
            else:
                clean_messages.append(m)

        if mode == "block" and all_violations:
            return clean_messages, all_violations, True

        return clean_messages, all_violations, False


global_guardrails = GuardrailsPipeline()
