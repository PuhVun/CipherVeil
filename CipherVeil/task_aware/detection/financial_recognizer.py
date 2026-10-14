"""
Financial Identifiers Recognizer for Presidio & Task-Aware Privacy.
Detects credit cards, bank accounts, routing numbers, and financial details.
"""

import re
from presidio_analyzer import EntityRecognizer, RecognizerResult


class FinancialRecognizer(EntityRecognizer):
    """Detects payment card numbers, bank account numbers, and routing numbers."""

    def __init__(self):
        super().__init__(
            supported_entities=["CREDIT_CARD_DETAILED", "BANK_ACCOUNT", "ROUTING_NUMBER"],
            name="FinancialRecognizer"
        )
        self._compile_patterns()

    def _compile_patterns(self):
        # Card number: 13 to 19 digits, possibly separated by spaces or dashes
        self.card_pattern = re.compile(
            r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|2(?:22[1-9]|2[3-9][0-9]|[3-6][0-9]{2}|7[0-1][0-9]|720)[0-9]{12}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12}|(?:2131|1800|35\d{3})\d{11}|(?:4[0-9]{3}|5[1-5][0-9]{2}|6011|7\d{3})(?:[- ]?[0-9]{4}){3}|3[47][0-9]{2}[- ]?[0-9]{6}[- ]?[0-9]{5})\b'
        )

        # Bank account context
        self.bank_account_pattern = re.compile(
            r'\b(?:account|acct|acc\.?|a\/c)(?:\s*(?:number|num|no\.?|#))?\s*[:=]?\s*([0-9]{6,17})\b',
            re.IGNORECASE
        )

        # Routing number (ABA 9 digits)
        self.routing_pattern = re.compile(
            r'\b(?:routing(?:\s*(?:number|num|no\.?|#))?|aba|routing\s+transit)\s*[:=]?\s*([0-9]{9})\b',
            re.IGNORECASE
        )

    def load(self):
        pass

    def analyze(self, text, entities, nlp_artifacts=None):
        results = []

        # Credit Cards
        if "CREDIT_CARD_DETAILED" in entities or "CREDIT_CARD" in entities:
            for match in self.card_pattern.finditer(text):
                clean_digits = re.sub(r'[\s-]', '', match.group(0))
                # Validate length for credit cards (13 to 19 digits)
                if 13 <= len(clean_digits) <= 19:
                    results.append(RecognizerResult(
                        entity_type="CREDIT_CARD",
                        start=match.start(),
                        end=match.end(),
                        score=0.98
                    ))

        # Bank Accounts
        if "BANK_ACCOUNT" in entities or "US_BANK_NUMBER" in entities:
            for match in self.bank_account_pattern.finditer(text):
                results.append(RecognizerResult(
                    entity_type="BANK_ACCOUNT",
                    start=match.start(1),
                    end=match.end(1),
                    score=0.98
                ))

        # Routing Numbers
        if "ROUTING_NUMBER" in entities:
            for match in self.routing_pattern.finditer(text):
                results.append(RecognizerResult(
                    entity_type="ROUTING_NUMBER",
                    start=match.start(1),
                    end=match.end(1),
                    score=0.95
                ))

        return results
