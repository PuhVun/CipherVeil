"""
Task Classification Engine for Task-Aware Privacy.
Identifies the user's intended task from the prompt to determine the appropriate privacy policy.
"""

import re
from typing import Dict, Any, List


class TaskClassifier:
    """Classifies user prompts into intent categories for privacy-preserving transformations."""

    TASK_CARD_BRAND = "CARD_BRAND_IDENTIFICATION"
    TASK_AGE_CALC = "AGE_DATE_CALCULATION"
    TASK_CODE_DEBUG = "CODE_DEBUGGING"
    TASK_FINANCIAL = "FINANCIAL_ANALYSIS"
    TASK_MEDICAL = "MEDICAL_ANALYSIS"
    TASK_DOC_GEN = "DOCUMENT_GENERATION"
    TASK_GENERAL = "GENERAL_QUERY"

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        # 1. Card Brand / Validation
        self.card_keywords = re.compile(
            r'\b(?:visa|mastercard|amex|american\s+express|discover|diners|jcb|card\s+(?:type|brand|issuer|number|company)|'
            r'which\s+card|what\s+card|is\s+this\s+(?:a|an)?\s*(?:visa|mastercard|amex|credit\s*card)|luhn|bin|iin|card\s*valid(?:ity)?)\b',
            re.IGNORECASE
        )

        # 2. Age / Date calculation
        self.age_keywords = re.compile(
            r'\b(?:how\s+old(?:\s+am\s+i|\s+is|\s+will|\s+are)?|calculate(?:\s+my)?\s+age|my\s+age|what\s+is\s+my\s+age|'
            r'age\s+from|years\s+old|date\s+of\s+birth|birthday\s+in|days\s+(?:until|since)\s+(?:my\s+)?birth(?:day|date)|'
            r'born\s+on\s+.*(?:how\s+old|what\s+age)|born\s+in\s+\d{4})\b',
            re.IGNORECASE
        )

        # 3. Code Debugging / Technical Syntax
        self.code_keywords = re.compile(
            r'\b(?:debug|fix\s+(?:this|my|the)?\s*code|error|syntaxerror|exception|traceback|401\s+unauthorized|invalid\s+request|'
            r'api[_-]?key|import\s+[a-z0-9_]+|def\s+[a-z0-9_]+|function\s*\(|const\s+[a-z0-9_]+|var\s+[a-z0-9_]+|'
            r'console\.log|print\(|curl\s+|fetch\(|axios\.|openai\.|anthropic\.|boto3|psycopg2|sqlalchemy|'
            r'connection\s+string|why\s+(?:is\s+this\s+failing|does\s+this\s+fail|am\s+i\s+getting\s+error))\b',
            re.IGNORECASE
        )

        # 4. Financial Analysis / Calculations
        self.financial_keywords = re.compile(
            r'\b(?:bank\s+statement|deposit(?:ed)?|withdrawal|expense[s]?|remaining\s+balance|total\s+balance|'
            r'spending|calculate\s+(?:my\s+)?(?:net|total|balance|savings|interest|tax|loan|roi)|statement|'
            r'account\s+balance|spent\s+on|transaction[s]?|income)\b',
            re.IGNORECASE
        )

        # 5. Medical Reports / Clinical Analysis
        self.medical_keywords = re.compile(
            r'\b(?:medical\s+report|doctor\s+note|lab\s+result[s]?|blood\s+(?:test|sugar|pressure)|glucose|'
            r'hba1c|cholesterol|mg\/dl|diagnosis|patient|mri|ct\s+scan|prescription|symptom[s]?|biopsy|'
            r'explain\s+(?:these|this|my)?\s*(?:findings|results|report|diagnosis|metrics))\b',
            re.IGNORECASE
        )

        # 6. Document Generation
        self.docgen_keywords = re.compile(
            r'\b(?:write|draft|create|generate|compose)\s+(?:a|an|the)?\s*(?:cover\s+letter|resume|cv|email|letter|'
            r'formal\s+letter|recommendation|statement\s+of\s+purpose|sop|nda|agreement|contract|bio|application)\b',
            re.IGNORECASE
        )

    def classify(self, text: str, detected_entities: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Classify prompt into task type with confidence and reasoning."""
        if not text:
            return {
                "task_type": self.TASK_GENERAL,
                "confidence": 0.5,
                "rationale": "Empty or default query."
            }

        detected_entities = detected_entities or []
        entity_types = {e["entity_type"] for e in detected_entities}

        scores = {
            self.TASK_CARD_BRAND: 0.0,
            self.TASK_AGE_CALC: 0.0,
            self.TASK_CODE_DEBUG: 0.0,
            self.TASK_FINANCIAL: 0.0,
            self.TASK_MEDICAL: 0.0,
            self.TASK_DOC_GEN: 0.0,
            self.TASK_GENERAL: 0.1
        }

        # --- Rule-Based Scoring ---

        # 1. Card Brand Identification
        if self.card_keywords.search(text):
            scores[self.TASK_CARD_BRAND] += 0.8
        if "CREDIT_CARD" in entity_types:
            scores[self.TASK_CARD_BRAND] += 0.4

        # 2. Age / Date calculation
        if self.age_keywords.search(text):
            scores[self.TASK_AGE_CALC] += 0.85
        if "DATE_OF_BIRTH" in entity_types:
            scores[self.TASK_AGE_CALC] += 0.35

        # 3. Code Debugging
        code_matches = len(self.code_keywords.findall(text))
        if code_matches > 0:
            scores[self.TASK_CODE_DEBUG] += min(0.9, 0.4 + code_matches * 0.15)
        if any(e in entity_types for e in ["API_KEY", "DATABASE_URL", "CRYPTO_KEY", "PASSWORD_CREDENTIAL"]):
            scores[self.TASK_CODE_DEBUG] += 0.3
        if "```" in text or "{" in text and "}" in text or "=" in text and ";" in text:
            scores[self.TASK_CODE_DEBUG] += 0.3

        # 4. Financial Analysis
        financial_matches = len(self.financial_keywords.findall(text))
        if financial_matches > 0:
            scores[self.TASK_FINANCIAL] += min(0.9, 0.4 + financial_matches * 0.2)
        if any(e in entity_types for e in ["BANK_ACCOUNT", "ROUTING_NUMBER", "US_BANK_NUMBER"]):
            scores[self.TASK_FINANCIAL] += 0.3

        # 5. Medical Analysis
        medical_matches = len(self.medical_keywords.findall(text))
        if medical_matches > 0:
            scores[self.TASK_MEDICAL] += min(0.95, 0.5 + medical_matches * 0.2)

        # 6. Document Generation
        if self.docgen_keywords.search(text):
            scores[self.TASK_DOC_GEN] += 0.9

        # Select highest scoring task
        sorted_tasks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_task, best_score = sorted_tasks[0]

        if best_score < 0.4:
            best_task = self.TASK_GENERAL
            best_score = 0.65

        confidence = min(0.99, max(0.6, round(best_score, 2)))

        rationales = {
            self.TASK_CARD_BRAND: "Prompt requests card issuer, brand, or validity check.",
            self.TASK_AGE_CALC: "Prompt asks to calculate age or date delta from a birth date.",
            self.TASK_CODE_DEBUG: "Prompt contains code snippets, syntax questions, or technical credentials to debug.",
            self.TASK_FINANCIAL: "Prompt requests calculation or analysis of financial balances, accounts, or statements.",
            self.TASK_MEDICAL: "Prompt asks to explain clinical lab reports, metrics, or medical diagnoses.",
            self.TASK_DOC_GEN: "Prompt requests drafting a formal personalized document (cover letter, resume, contract).",
            self.TASK_GENERAL: "General conversational query containing personal context."
        }

        return {
            "task_type": best_task,
            "confidence": confidence,
            "rationale": rationales.get(best_task, "Classified based on keywords and entities.")
        }
