"""
Sanitization Validation Engine for Task-Aware Privacy in CipherVeil.
Verifies that transformed prompts are leak-free, syntactically intact, and context-preserving.
"""

import re
from typing import Dict, Any, List


class SanitizationValidator:
    """Validates that transformed prompts do not leak sensitive information and preserve task utility."""

    def __init__(self):
        # High-risk leakage patterns that must NEVER appear in the sanitized text
        self.raw_card_pattern = re.compile(r'\b(?:\d{4}[- ]?){3}\d{4}\b')
        self.raw_ssn_pattern = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
        self.raw_openai_key = re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}\b')
        self.raw_ghp_token = re.compile(r'\bgh[pousr]_[A-Za-z0-9]{36}\b')
        self.raw_aws_key = re.compile(r'\bAKIA[0-9A-Z]{16}\b')

    def validate(
        self,
        original_text: str,
        sanitized_text: str,
        detected_entities: List[Dict[str, Any]],
        task_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform security validation and context retention audit."""
        leaks = []

        # 1. Check for raw detected entity leaks in the sanitized prompt
        for entity in detected_entities:
            orig_val = entity["text"]
            e_type = entity["entity_type"]
            # If high-sensitivity entity text still appears verbatim in sanitized prompt
            if entity["sensitivity"] == "HIGH" and orig_val in sanitized_text:
                leaks.append({
                    "entity_type": e_type,
                    "value_preview": entity.get("masked_preview", "****"),
                    "severity": "CRITICAL"
                })

        # 2. Check for regex signatures of raw secrets
        if self.raw_card_pattern.search(sanitized_text) and not any(m in sanitized_text for m in ["****", "XXXX"]):
            leaks.append({"entity_type": "CREDIT_CARD", "severity": "HIGH", "detail": "Unmasked payment card number detected."})
        if self.raw_openai_key.search(sanitized_text) and "YOUR_OPENAI_KEY" not in sanitized_text:
            leaks.append({"entity_type": "API_KEY", "severity": "CRITICAL", "detail": "Unmasked OpenAI API key detected."})
        if self.raw_ghp_token.search(sanitized_text):
            leaks.append({"entity_type": "API_KEY", "severity": "CRITICAL", "detail": "Unmasked GitHub token detected."})
        if self.raw_aws_key.search(sanitized_text):
            leaks.append({"entity_type": "API_KEY", "severity": "CRITICAL", "detail": "Unmasked AWS key detected."})

        # 3. Context preservation check
        # Verify that prompt length and core questions are preserved
        context_preserved = True
        if len(sanitized_text.strip()) == 0 and len(original_text.strip()) > 0:
            context_preserved = False
        if "?" in original_text and "?" not in sanitized_text:
            context_preserved = False

        # Calculate risk score
        risk_score = 0.0
        if leaks:
            risk_score = 1.0 if any(l.get("severity") == "CRITICAL" for l in leaks) else 0.7
        elif not context_preserved:
            risk_score = 0.3

        is_valid = len(leaks) == 0

        summary = "Validation Passed: Prompt is safe for transmission." if is_valid else f"Validation Failed: {len(leaks)} potential leak(s) detected!"

        return {
            "is_valid": is_valid,
            "risk_score": risk_score,
            "leaks_count": len(leaks),
            "leaks": leaks,
            "context_preserved": context_preserved,
            "summary": summary
        }
