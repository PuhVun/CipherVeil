"""
Date of Birth (DOB) Recognizer for Presidio & Task-Aware Privacy.
Distinguishes specific Dates of Birth from general dates/times.
"""

import re
from presidio_analyzer import EntityRecognizer, RecognizerResult


class DOBRecognizer(EntityRecognizer):
    """Detects Date of Birth occurrences with conversational context and explicit markers."""

    def __init__(self):
        super().__init__(
            supported_entities=["DATE_OF_BIRTH"],
            name="DOBRecognizer"
        )
        self._compile_patterns()

    def _compile_patterns(self):
        # Conversational markers preceding dates
        # e.g., "born on 1990-05-14", "born May 14, 1990", "DOB: 12/03/1985", "date of birth: 2001-04-12"
        date_regex = (
            r'(?:'
            r'\d{4}[-/.]\d{1,2}[-/.]\d{1,2}'                           # YYYY-MM-DD
            r'|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}'                       # MM/DD/YYYY or DD/MM/YYYY
            r'|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
            r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
            r'\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}'                    # Month DD, YYYY
            r'|\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
            r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?),?\s+\d{4}' # DD Month YYYY
            r')'
        )

        self.dob_prefix_pattern = re.compile(
            r'\b(?:born\s+(?:on|in)?|d\.?o\.?b\.?(?:\s*[:=])?|date\s+of\s+birth(?:\s*[:=])?|birth\s*date(?:\s*[:=])?|birthday(?:\s+(?:is|on|was))?(?:\s*[:=])?)\s*(' + date_regex + r')\b',
            re.IGNORECASE
        )

        self.dob_postfix_pattern = re.compile(
            r'\b(' + date_regex + r')\s+(?:is\s+my\s+birth(?:day|date)|is\s+my\s+d\.?o\.?b\.?|was\s+the\s+day\s+I\s+was\s+born)\b',
            re.IGNORECASE
        )

    def load(self):
        pass

    def analyze(self, text, entities, nlp_artifacts=None):
        results = []
        if "DATE_OF_BIRTH" not in entities:
            return results

        # Prefix pattern
        for match in self.dob_prefix_pattern.finditer(text):
            date_str = match.group(1)
            results.append(RecognizerResult(
                entity_type="DATE_OF_BIRTH",
                start=match.start(1),
                end=match.end(1),
                score=0.98
            ))

        # Postfix pattern
        for match in self.dob_postfix_pattern.finditer(text):
            date_str = match.group(1)
            results.append(RecognizerResult(
                entity_type="DATE_OF_BIRTH",
                start=match.start(1),
                end=match.end(1),
                score=0.95
            ))

        return results
