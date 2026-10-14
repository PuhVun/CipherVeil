"""
Detection engine for Task-Aware Privacy in CipherVeil.
Combines Presidio AnalyzerEngine with specialized recognizers for
secrets, technical credentials, dates of birth, and financial identifiers.
"""

import re
from typing import List, Dict, Any, Optional
from presidio_analyzer import AnalyzerEngine, EntityRecognizer, RecognizerResult

from .secrets_recognizer import SecretsRecognizer
from .dob_recognizer import DOBRecognizer
from .financial_recognizer import FinancialRecognizer


class EnhancedPersonRecognizer(EntityRecognizer):
    """Custom Presidio recognizer for conversational and casual name contexts."""

    def __init__(self):
        super().__init__(supported_entities=['PERSON'], name='EnhancedPersonRecognizer')
        self.greetings = re.compile(r'\b(?:hey+|hi+|hello+|dear|hola|howdy|yo+)\s+([A-Za-z0-9_-]+)', re.IGNORECASE)
        self.intros = re.compile(
            r'\b(?:i\s+am|my\s+name\s+is|this\s+is|call\s+me|i\'m|im)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)',
            re.IGNORECASE
        )
        self.common_names = {
            'sam', 'sami','devarajan','singh',
            'rahul', 'priya', 'aarav', 'ananya', 'alex', 'john', 'david',
            'sarah', 'emily', 'michael', 'jessica', 'karen', 'robert'
        }

    def load(self):
        pass

    def analyze(self, text, entities, nlp_artifacts=None):
        results = []
        if 'PERSON' not in entities:
            return results

        # 1. Names following greetings (e.g., "HEYYYY SAMMMM", "hey alex")
        for match in self.greetings.finditer(text):
            word = match.group(1)
            if word.lower() not in {'there', 'everyone', 'everybody', 'guys', 'all', 'bot', 'assistant'}:
                results.append(RecognizerResult(
                    entity_type='PERSON',
                    start=match.start(1),
                    end=match.end(1),
                    score=0.95
                ))

        # 2. Names following introductions (e.g., "I am Samvritha Devarajan", "My name is John")
        for match in self.intros.finditer(text):
            results.append(RecognizerResult(
                entity_type='PERSON',
                start=match.start(1),
                end=match.end(1),
                score=0.95
            ))

        # 3. Common names
        for word_match in re.finditer(r'\b([A-Za-z]{2,})\b', text):
            word = word_match.group(1)
            norm = re.sub(r'(.)\1+', r'\1', word.lower())
            if word.lower() in self.common_names or norm in self.common_names:
                results.append(RecognizerResult(
                    entity_type='PERSON',
                    start=word_match.start(1),
                    end=word_match.end(1),
                    score=0.92
                ))

        return results


class TaskAwareDetectionEngine:
    """Unified sensitive information detection engine."""

    SENSITIVITY_MAP = {
        "API_KEY": "HIGH",
        "PASSWORD_CREDENTIAL": "HIGH",
        "DATABASE_URL": "HIGH",
        "CRYPTO_KEY": "HIGH",
        "CREDIT_CARD": "HIGH",
        "US_SSN": "HIGH",
        "BANK_ACCOUNT": "MEDIUM",
        "ROUTING_NUMBER": "MEDIUM",
        "US_BANK_NUMBER": "MEDIUM",
        "DATE_OF_BIRTH": "MEDIUM",
        "EMAIL_ADDRESS": "MEDIUM",
        "PHONE_NUMBER": "MEDIUM",
        "MEDICAL_LICENSE": "MEDIUM",
        "PERSON": "LOW",
        "LOCATION": "LOW",
        "DATE_TIME": "LOW",
        "IP_ADDRESS": "LOW",
    }

    TYPE_PRIORITY = {
        "CRYPTO_KEY": 100,
        "API_KEY": 95,
        "PASSWORD_CREDENTIAL": 90,
        "DATABASE_URL": 85,
        "CREDIT_CARD": 80,
        "US_SSN": 80,
        "BANK_ACCOUNT": 70,
        "ROUTING_NUMBER": 70,
        "DATE_OF_BIRTH": 65,
        "EMAIL_ADDRESS": 60,
        "PHONE_NUMBER": 55,
        "PERSON": 50,
        "LOCATION": 40,
        "DATE_TIME": 30,
        "IP_ADDRESS": 20,
    }

    def __init__(self):
        self.analyzer = AnalyzerEngine()
        self.analyzer.registry.add_recognizer(EnhancedPersonRecognizer())
        self.analyzer.registry.add_recognizer(SecretsRecognizer())
        self.analyzer.registry.add_recognizer(DOBRecognizer())
        self.analyzer.registry.add_recognizer(FinancialRecognizer())

    def get_supported_entities(self) -> List[str]:
        return list(self.TYPE_PRIORITY.keys())

    def detect(self, text: str, requested_entities: Optional[List[str]] = None, language: str = "en") -> List[Dict[str, Any]]:
        """
        Detect all sensitive entities, resolve overlapping spans,
        and assign sensitivity ratings and masked previews.
        """
        if not text:
            return []

        if not requested_entities:
            # Query all supported entities by default
            requested_entities = self.get_supported_entities()

        raw_results = self.analyzer.analyze(
            text=text,
            entities=requested_entities,
            language=language
        )

        # Also apply explicit rule check for card patterns if raw_results missed
        # or if Presidio needs reinforcement
        financial_rec = FinancialRecognizer()
        extra_financial = financial_rec.analyze(text, ["CREDIT_CARD", "BANK_ACCOUNT", "ROUTING_NUMBER"])
        raw_results.extend(extra_financial)

        # Resolve overlapping spans with priority
        resolved_results = self._resolve_overlapping_spans(raw_results, text)

        entities_output = []
        for r in resolved_results:
            original_val = text[r.start:r.end]
            sensitivity = self.SENSITIVITY_MAP.get(r.entity_type, "MEDIUM")
            masked_preview = self._make_preview(r.entity_type, original_val)

            entities_output.append({
                "entity_type": r.entity_type,
                "start": r.start,
                "end": r.end,
                "score": round(r.score, 3),
                "text": original_val,
                "sensitivity": sensitivity,
                "masked_preview": masked_preview
            })

        return entities_output

    def _resolve_overlapping_spans(self, results: List[RecognizerResult], text: str) -> List[RecognizerResult]:
        """Resolves overlapping entity spans with priority on entity type and confidence."""
        if not results:
            return []

        def sort_key(res: RecognizerResult):
            type_prio = self.TYPE_PRIORITY.get(res.entity_type, 10)
            span_len = res.end - res.start
            return (res.start, -type_prio, -res.score, -span_len)

        sorted_results = sorted(results, key=sort_key)
        filtered: List[RecognizerResult] = []
        last_end = -1

        for r in sorted_results:
            if r.start >= last_end:
                filtered.append(r)
                last_end = r.end
            else:
                # Overlap detected
                prev = filtered[-1]
                prev_prio = self.TYPE_PRIORITY.get(prev.entity_type, 10)
                curr_prio = self.TYPE_PRIORITY.get(r.entity_type, 10)

                if (curr_prio > prev_prio) or (curr_prio == prev_prio and r.score > prev.score):
                    filtered[-1] = r
                    last_end = r.end

        return filtered

    def _make_preview(self, entity_type: str, text: str) -> str:
        """Create a safe masked preview for user transparency."""
        if entity_type == "CREDIT_CARD":
            clean = re.sub(r'[\s-]', '', text)
            if len(clean) >= 4:
                return f"{clean[:4]}****{clean[-4:]}"
            return "****"
        elif entity_type in ["API_KEY", "PASSWORD_CREDENTIAL"]:
            if len(text) > 8:
                return f"{text[:4]}...{text[-4:]}"
            return "****"
        elif entity_type == "EMAIL_ADDRESS":
            parts = text.split('@')
            if len(parts) == 2 and len(parts[0]) > 2:
                return f"{parts[0][:2]}***@{parts[1]}"
            return "***@***.com"
        elif entity_type == "PHONE_NUMBER":
            clean = re.sub(r'\D', '', text)
            if len(clean) >= 4:
                return f"***-***-{clean[-4:]}"
            return "***-***-****"
        elif entity_type == "DATE_OF_BIRTH":
            return "**/**/****"
        return text[:2] + "****" if len(text) > 3 else "****"
