"""
Comprehensive Secrets and Technical Credentials Recognizer for Presidio & Task-Aware Privacy.
Detects API keys, access tokens, passwords, database URLs, and private keys with
pattern matching, entropy validation, and calibrated confidence scoring.
"""

import math
import re
from typing import List, Optional
from presidio_analyzer import EntityRecognizer, RecognizerResult


def calculate_shannon_entropy(data: str) -> float:
    """Calculate Shannon entropy of a string to evaluate randomness/cryptographic strength."""
    if not data:
        return 0.0
    entropy = 0.0
    length = len(data)
    char_counts = {}
    for char in data:
        char_counts[char] = char_counts.get(char, 0) + 1
    for count in char_counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def is_placeholder(val: str) -> bool:
    """Check if the detected value is an obvious placeholder or dummy text."""
    v = val.lower().strip()
    if len(v) < 6:
        return True

    if 'placeholder' in v:
        return True

    dummy_prefixes = (
        'your_', 'your-', 'dummy_', 'dummy-', 'fake_', 'fake-',
        'replace_', 'insert_', 'sample_', 'my_api_key', 'my_secret'
    )
    if any(v.startswith(p) for p in dummy_prefixes):
        return True

    exact_dummies = {
        'xxxxxx', '000000', '12345678', 'password', 'admin', 'secret',
        'changeme', 'secret_key', 'api_key', 'access_token'
    }
    if v in exact_dummies:
        return True

    # Check for simple monotonic or repeated characters (e.g., 'aaaaaa', '111111')
    if len(set(v)) <= 2:
        return True

    return False


class SecretsRecognizer(EntityRecognizer):
    """
    Dedicated production-grade secret detection engine.
    Detects:
      - AI & Cloud Provider API Keys (OpenAI, Anthropic, Google/Firebase, HuggingFace, AWS, Stripe, Slack, Twilio, SendGrid, GitHub)
      - Generic API Keys, Bearer Tokens, JWTs, and Access Tokens
      - Passwords and Database Credentials (including embedded connection string passwords)
      - Cryptographic Private Keys (PEM, OpenSSH, PGP, escaped multi-line)
    """

    def __init__(self):
        super().__init__(
            supported_entities=["API_KEY", "PASSWORD_CREDENTIAL", "DATABASE_URL", "CRYPTO_KEY"],
            name="SecretsRecognizer"
        )
        self._compile_patterns()

    def _compile_patterns(self):
        # 1. Exact Provider Key Patterns (High Confidence >= 0.98)
        # OpenAI: legacy 'sk-...', project 'sk-proj-...', svcacct 'sk-svcacct-...', admin 'sk-admin-...'
        self.openai_pattern = re.compile(
            r'\b(sk-(?:proj-|svcacct-|admin-|live-|test-)?[A-Za-z0-9_-]{20,})\b'
        )
        # Anthropic Claude: 'sk-ant-api03-...', 'sk-ant-admin01-...'
        self.anthropic_pattern = re.compile(
            r'\b(sk-ant-(?:api\d{2}-|admin\d{2}-)?[A-Za-z0-9_-]{32,})\b'
        )
        # Google AI Studio / Firebase / Maps: 'AIzaSy...'
        self.google_pattern = re.compile(
            r'\b(AIzaSy[A-Za-z0-9_-]{33})\b'
        )
        # GitHub: classic ghp, fine-grained github_pat, OAuth gho, user ghu, server ghs, refresh ghr
        self.github_pattern = re.compile(
            r'\b(gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})\b'
        )
        # AWS Access Key ID
        self.aws_key_pattern = re.compile(
            r'\b((?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16})\b'
        )
        # AWS Secret Access Key in key-value context (40 base64 chars)
        self.aws_secret_pattern = re.compile(
            r'(?:aws_secret_access_key|aws_secret|secret_key|aws_secret_key)\s*[:=]\s*[\'"]?([A-Za-z0-9/+=]{40})[\'"]?',
            re.IGNORECASE
        )
        # Stripe API Keys (Live & Test, Secret & Restricted)
        self.stripe_pattern = re.compile(
            r'\b((?:sk|rk)_(?:live|test)_[0-9a-zA-Z]{24,})\b'
        )
        # Slack Tokens (bot, user, app)
        self.slack_pattern = re.compile(
            r'\b(xox[baprs]-[0-9A-Za-z-]{10,})\b'
        )
        # HuggingFace User Access Tokens
        self.hf_pattern = re.compile(
            r'\b(hf_[A-Za-z0-9]{34,})\b'
        )
        # Twilio API Credentials
        self.twilio_pattern = re.compile(
            r'\b(AC[a-f0-9]{32}|SK[a-f0-9]{32})\b'
        )
        # SendGrid API Key
        self.sendgrid_pattern = re.compile(
            r'\b(SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43})\b'
        )

        # 2. Bearer & JWT Tokens
        self.bearer_pattern = re.compile(
            r'\bBearer\s+([A-Za-z0-9\-\._~\+\/]{20,}=*)\b',
            re.IGNORECASE
        )
        self.jwt_pattern = re.compile(
            r'\b(eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b'
        )

        # 3. Generic Key / Token Assignments in Code, Config, JSON, YAML
        self.generic_assignment_pattern = re.compile(
            r'(?:[\'"\b])?'
            r'(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|secret[_-]?key|private[_-]?token|app[_-]?secret)'
            r'(?:[\'"\b])?'
            r'\s*[:=]\s*'
            r'[\'"]([A-Za-z0-9_\-\.]{14,})[\'"]',
            re.IGNORECASE
        )

        # 4. Database Connection Strings (Postgres, MySQL, MongoDB, Redis, etc.)
        self.db_url_pattern = re.compile(
            r'((?:postgres|postgresql|mysql|mongodb(?:\+srv)?|redis|rediss|mssql|oracle|amqp|amqps):\/\/'
            r'([^:\s\'\"]+):(?P<pwd>[^@\s\'\"]+)@'
            r'([A-Za-z0-9_\-\.]+)(?::([0-9]+))?(?:\/([^\s\'\"\)]*))?)',
            re.IGNORECASE
        )

        # 5. Passwords in Code, JSON, YAML, Env
        self.password_assignment_pattern = re.compile(
            r'(?:[\'"\b])?'
            r'(?:password|passwd|pwd|db_pass(?:word)?|user_password|secret_password|admin_password)'
            r'(?:[\'"\b])?'
            r'\s*[:=]\s*'
            r'[\'"]([^\'"\s]{4,})[\'"]',
            re.IGNORECASE
        )

        # 6. Cryptographic Private Keys (Multi-line and Escaped \n)
        self.priv_key_pattern = re.compile(
            r'-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY(?: BLOCK)?-----(?:[\s\S]+?|.+?)-----END (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY(?: BLOCK)?-----'
        )

    def load(self):
        pass

    def analyze(self, text: str, entities: List[str], nlp_artifacts=None) -> List[RecognizerResult]:
        results: List[RecognizerResult] = []
        if not text:
            return results

        matched_spans = set()

        # ----------------------------------------------------
        # 1. API Keys & Technical Tokens
        # ----------------------------------------------------
        if "API_KEY" in entities:
            # High-confidence exact provider signatures
            provider_checks = [
                (self.openai_pattern, 0.99),
                (self.anthropic_pattern, 0.99),
                (self.google_pattern, 0.98),
                (self.github_pattern, 0.99),
                (self.aws_key_pattern, 0.98),
                (self.aws_secret_pattern, 0.96),
                (self.stripe_pattern, 0.99),
                (self.slack_pattern, 0.98),
                (self.hf_pattern, 0.98),
                (self.twilio_pattern, 0.95),
                (self.sendgrid_pattern, 0.99),
                (self.jwt_pattern, 0.97),
                (self.bearer_pattern, 0.95),
            ]

            for pattern, base_score in provider_checks:
                for match in pattern.finditer(text):
                    val = match.group(1) if match.groups() else match.group(0)
                    start = match.start(1) if match.groups() else match.start()
                    end = match.end(1) if match.groups() else match.end()

                    if is_placeholder(val):
                        continue

                    matched_spans.add((start, end))
                    results.append(RecognizerResult(
                        entity_type="API_KEY",
                        start=start,
                        end=end,
                        score=base_score
                    ))

            # Generic Key Assignments with Entropy Calibration
            for match in self.generic_assignment_pattern.finditer(text):
                val = match.group(1)
                start = match.start(1)
                end = match.end(1)

                if (start, end) in matched_spans or is_placeholder(val):
                    continue

                entropy = calculate_shannon_entropy(val)
                # Calibrate confidence based on entropy and length
                if entropy >= 3.5:
                    score = 0.95
                elif entropy >= 3.0:
                    score = 0.88
                elif entropy >= 2.5:
                    score = 0.75
                else:
                    score = 0.55  # Lower confidence for repetitive/dictionary strings

                matched_spans.add((start, end))
                results.append(RecognizerResult(
                    entity_type="API_KEY",
                    start=start,
                    end=end,
                    score=score
                ))

        # ----------------------------------------------------
        # 2. Database Connection Strings & Embedded Passwords
        # ----------------------------------------------------
        if "DATABASE_URL" in entities or "PASSWORD_CREDENTIAL" in entities:
            for match in self.db_url_pattern.finditer(text):
                full_url = match.group(1)
                url_start = match.start(1)
                url_end = match.end(1)

                if "DATABASE_URL" in entities:
                    results.append(RecognizerResult(
                        entity_type="DATABASE_URL",
                        start=url_start,
                        end=url_end,
                        score=0.97
                    ))

                # Also specifically extract the embedded password
                pwd_span = match.span('pwd')
                if pwd_span and pwd_span[0] != -1 and "PASSWORD_CREDENTIAL" in entities:
                    pwd_val = text[pwd_span[0]:pwd_span[1]]
                    if not is_placeholder(pwd_val):
                        results.append(RecognizerResult(
                            entity_type="PASSWORD_CREDENTIAL",
                            start=pwd_span[0],
                            end=pwd_span[1],
                            score=0.96
                        ))

        # ----------------------------------------------------
        # 3. Explicit Password Assignments
        # ----------------------------------------------------
        if "PASSWORD_CREDENTIAL" in entities:
            for match in self.password_assignment_pattern.finditer(text):
                val = match.group(1)
                start = match.start(1)
                end = match.end(1)

                if is_placeholder(val):
                    continue

                entropy = calculate_shannon_entropy(val)
                score = 0.95 if entropy >= 3.0 else 0.88

                results.append(RecognizerResult(
                    entity_type="PASSWORD_CREDENTIAL",
                    start=start,
                    end=end,
                    score=score
                ))

        # ----------------------------------------------------
        # 4. Cryptographic Private Keys
        # ----------------------------------------------------
        if "CRYPTO_KEY" in entities:
            for match in self.priv_key_pattern.finditer(text):
                results.append(RecognizerResult(
                    entity_type="CRYPTO_KEY",
                    start=match.start(),
                    end=match.end(),
                    score=1.0
                ))

        return results
