"""
Task-Specific Privacy Policy Engine for CipherVeil.
Determines entity necessity, allowed transformations, and selects optimal strategy
based on classified task and detected sensitive information.
"""

from typing import Dict, Any, List


class PrivacyPolicyEngine:
    """Evaluates task context and determines privacy policies and transformation strategies."""

    STRATEGY_LOCAL_COMPUTE = "LOCAL_COMPUTATION"
    STRATEGY_SYNTAX_PLACEHOLDER = "SYNTAX_PRESERVING_PLACEHOLDER"
    STRATEGY_PROPERTY_MASK = "PROPERTY_PRESERVING_MASK"
    STRATEGY_REVERSIBLE_PSEUDONYM = "REVERSIBLE_PSEUDONYMIZATION"
    STRATEGY_SELECTIVE_REDACT = "SELECTIVE_REDACTION"
    STRATEGY_GENERAL_ANONYMIZE = "GENERAL_ANONYMIZATION"

    def evaluate(self, task_info: Dict[str, Any], detected_entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Determine privacy policy, entity necessity, and transformation strategy."""
        task_type = task_info.get("task_type", "GENERAL_QUERY")
        entity_types = {e["entity_type"] for e in detected_entities}

        policy = {
            "task_type": task_type,
            "strategy": self.STRATEGY_GENERAL_ANONYMIZE,
            "necessary_entities": [],
            "unnecessary_entities": list(entity_types),
            "can_local_compute": False,
            "explanation": "Default anonymization applied."
        }

        # 1. Card Brand Identification
        if task_type == "CARD_BRAND_IDENTIFICATION":
            if "CREDIT_CARD" in entity_types:
                policy["strategy"] = self.STRATEGY_LOCAL_COMPUTE
                policy["can_local_compute"] = True
                policy["necessary_entities"] = []  # Raw 16 digits are NOT needed by external AI!
                policy["unnecessary_entities"] = ["CREDIT_CARD"]
                policy["explanation"] = (
                    "Card brand and Luhn validity can be resolved 100% locally. "
                    "Full card number is unnecessary for external AI and should never be transmitted."
                )

        # 2. Age / Date calculation
        elif task_type == "AGE_DATE_CALCULATION":
            if "DATE_OF_BIRTH" in entity_types or "DATE_TIME" in entity_types:
                policy["strategy"] = self.STRATEGY_LOCAL_COMPUTE
                policy["can_local_compute"] = True
                policy["necessary_entities"] = []
                policy["unnecessary_entities"] = ["DATE_OF_BIRTH", "DATE_TIME"]
                policy["explanation"] = (
                    "Age calculation can be completed locally. "
                    "Sharing exact birth date with external AI is unnecessary and poses identity risks."
                )

        # 3. Code Debugging with Technical Credentials
        elif task_type == "CODE_DEBUGGING":
            technical_secrets = {"API_KEY", "PASSWORD_CREDENTIAL", "DATABASE_URL", "CRYPTO_KEY"}
            found_secrets = entity_types.intersection(technical_secrets)
            if found_secrets:
                policy["strategy"] = self.STRATEGY_SYNTAX_PLACEHOLDER
                policy["can_local_compute"] = False
                policy["necessary_entities"] = []  # Secrets are NEVER needed for syntax or code logic debugging!
                policy["unnecessary_entities"] = list(found_secrets)
                policy["explanation"] = (
                    "Real credentials are not needed to debug code logic or syntax. "
                    "Replacing secrets with syntax-preserving dummy placeholders maintains code validity without leakage."
                )

        # 4. Financial Analysis / Statements
        elif task_type == "FINANCIAL_ANALYSIS":
            policy["strategy"] = self.STRATEGY_PROPERTY_MASK
            policy["can_local_compute"] = True  # Can attempt local arithmetic balance check
            policy["necessary_entities"] = []
            policy["unnecessary_entities"] = [e for e in entity_types if e in ["BANK_ACCOUNT", "ROUTING_NUMBER", "US_SSN", "PERSON"]]
            policy["explanation"] = (
                "Financial calculations need amounts, but bank account numbers and personal identifiers are unnecessary."
            )

        # 5. Medical Reports
        elif task_type == "MEDICAL_ANALYSIS":
            policy["strategy"] = self.STRATEGY_SELECTIVE_REDACT
            policy["can_local_compute"] = False
            # Patient names, DOBs, and phone numbers are completely unnecessary for medical explanation
            policy["necessary_entities"] = []
            policy["unnecessary_entities"] = [e for e in entity_types if e in ["PERSON", "DATE_OF_BIRTH", "PHONE_NUMBER", "LOCATION", "US_SSN"]]
            policy["explanation"] = (
                "Patient identifiers are completely unnecessary for explaining medical diagnosis or lab metrics. "
                "Identifiers are selectively redacted while clinical terminology and units are preserved."
            )

        # 6. Document Generation
        elif task_type == "DOCUMENT_GENERATION":
            policy["strategy"] = self.STRATEGY_REVERSIBLE_PSEUDONYM
            policy["can_local_compute"] = False
            # AI needs placeholders, but user needs real values restored on response
            policy["necessary_entities"] = []
            policy["unnecessary_entities"] = list(entity_types)
            policy["explanation"] = (
                "Personal details in generated documents are shielded with realistic synthetic values "
                "and automatically restored in the AI response."
            )

        # 7. General Query
        else:
            policy["strategy"] = self.STRATEGY_GENERAL_ANONYMIZE
            policy["explanation"] = "General query: Personal identifiers are pseudonymized or redacted based on user preference."

        return policy
