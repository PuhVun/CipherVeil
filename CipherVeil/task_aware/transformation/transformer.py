"""
Transformation Engine for Task-Aware Privacy in CipherVeil.
Applies context-aware transformations: Local computation, syntax-preserving placeholders,
property-preserving masks, reversible pseudonymization, or selective redaction.
"""

from typing import Dict, Any, List, Tuple
from faker import Faker
import re

from .local_solvers import CreditCardLocalSolver, AgeLocalSolver, FinancialLocalSolver

fake = Faker()


class TaskAwareTransformer:
    """Executes task-aware transformations on user prompts."""

    def __init__(self):
        pass

    def transform(
        self,
        text: str,
        task_info: Dict[str, Any],
        policy: Dict[str, Any],
        detected_entities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Transform user prompt based on task context and privacy policy."""
        strategy = policy.get("strategy", "GENERAL_ANONYMIZATION")
        task_type = task_info.get("task_type", "GENERAL_QUERY")

        result = {
            "strategy": strategy,
            "original_text": text,
            "sanitized_text": text,
            "local_answer": None,
            "can_answer_locally": False,
            "mappings": {},
            "explanation": policy.get("explanation", "")
        }

        # --- 1. LOCAL COMPUTATION STRATEGY ---
        if strategy == "LOCAL_COMPUTATION" or policy.get("can_local_compute", False):
            # A. Credit Card Brand / Validation check
            if task_type == "CARD_BRAND_IDENTIFICATION":
                cards = [e for e in detected_entities if e["entity_type"] == "CREDIT_CARD"]
                if cards:
                    card_text = cards[0]["text"]
                    local_res = CreditCardLocalSolver.solve(text, card_text)
                    if local_res.get("can_solve_locally"):
                        result["can_answer_locally"] = True
                        result["local_answer"] = local_res.get("answer")

                    # Also create safe property-preserving sanitized prompt if forwarded to AI
                    clean_digits = re.sub(r'\D', '', card_text)
                    brand = CreditCardLocalSolver.identify_brand(clean_digits)
                    safe_mask = f"{clean_digits[:4]} **** **** {clean_digits[-4:]} ({brand} card)"
                    result["sanitized_text"] = text.replace(card_text, safe_mask)
                    result["mappings"][safe_mask] = card_text
                    return result

            # B. Age / Date calculation
            elif task_type == "AGE_DATE_CALCULATION":
                dobs = [e for e in detected_entities if e["entity_type"] in ["DATE_OF_BIRTH", "DATE_TIME"]]
                if dobs:
                    dob_text = dobs[0]["text"]
                    local_res = AgeLocalSolver.solve(text, dob_text)
                    if local_res.get("can_solve_locally"):
                        result["can_answer_locally"] = True
                        result["local_answer"] = local_res.get("answer")

                    # Safe relative year / age substitution if forwarded
                    age_years = local_res.get("age_years", 30)
                    safe_mask = f"[Age: {age_years} years old]"
                    result["sanitized_text"] = text.replace(dob_text, safe_mask)
                    result["mappings"][safe_mask] = dob_text
                    return result

            # C. Financial arithmetic
            elif task_type == "FINANCIAL_ANALYSIS":
                local_res = FinancialLocalSolver.solve(text)
                if local_res.get("can_solve_locally"):
                    result["can_answer_locally"] = True
                    result["local_answer"] = local_res.get("answer")

        # --- 2. SYNTAX-PRESERVING PLACEHOLDER STRATEGY (Code Debugging) ---
        if strategy == "SYNTAX_PRESERVING_PLACEHOLDER":
            sanitized = text
            # Sort from right to left to preserve offsets
            for entity in sorted(detected_entities, key=lambda x: x["start"], reverse=True):
                orig_val = entity["text"]
                e_type = entity["entity_type"]

                if e_type == "API_KEY":
                    # Determine provider prefix for clarity in debugging
                    if orig_val.startswith("sk-proj-"):
                        placeholder = "sk-proj-YOUR_OPENAI_KEY_PLACEHOLDER"
                    elif orig_val.startswith("sk-ant-"):
                        placeholder = "sk-ant-YOUR_ANTHROPIC_KEY_PLACEHOLDER"
                    elif orig_val.startswith("ghp_"):
                        placeholder = "ghp_YOUR_GITHUB_TOKEN_PLACEHOLDER"
                    elif orig_val.startswith("AKIA"):
                        placeholder = "AKIA_YOUR_AWS_KEY_ID_PLACEHOLDER"
                    else:
                        placeholder = "YOUR_API_KEY_HERE"
                elif e_type == "PASSWORD_CREDENTIAL":
                    placeholder = "YOUR_DATABASE_PASSWORD_HERE"
                elif e_type == "DATABASE_URL":
                    placeholder = "postgresql://user:YOUR_PASSWORD@db.example.internal:5432/main"
                elif e_type == "CRYPTO_KEY":
                    placeholder = "-----BEGIN PRIVATE KEY-----\n[REDACTED_CRYPTO_KEY]\n-----END PRIVATE KEY-----"
                else:
                    placeholder = f"REDACTED_{e_type}"

                sanitized = sanitized[:entity["start"]] + placeholder + sanitized[entity["end"]:]
                result["mappings"][placeholder] = orig_val

            result["sanitized_text"] = sanitized
            return result

        # --- 3. PROPERTY-PRESERVING MASK STRATEGY (Financial / Card) ---
        if strategy == "PROPERTY_PRESERVING_MASK":
            sanitized = text
            for entity in sorted(detected_entities, key=lambda x: x["start"], reverse=True):
                orig_val = entity["text"]
                e_type = entity["entity_type"]

                if e_type in ["BANK_ACCOUNT", "US_BANK_NUMBER"]:
                    placeholder = f"[ACCOUNT_****{orig_val[-4:] if len(orig_val) >= 4 else 'XXXX'}]"
                elif e_type == "ROUTING_NUMBER":
                    placeholder = "[ROUTING_NUMBER_REDACTED]"
                elif e_type == "CREDIT_CARD":
                    clean = re.sub(r'\D', '', orig_val)
                    placeholder = f"{clean[:4]} **** **** {clean[-4:] if len(clean) >= 4 else ''}"
                else:
                    placeholder = f"[REDACTED_{e_type}]"

                sanitized = sanitized[:entity["start"]] + placeholder + sanitized[entity["end"]:]
                result["mappings"][placeholder] = orig_val

            result["sanitized_text"] = sanitized
            return result

        # --- 4. SELECTIVE REDACTION STRATEGY (Medical Analysis) ---
        if strategy == "SELECTIVE_REDACTION":
            sanitized = text
            for entity in sorted(detected_entities, key=lambda x: x["start"], reverse=True):
                orig_val = entity["text"]
                e_type = entity["entity_type"]

                if e_type == "PERSON":
                    placeholder = "[PATIENT_NAME]"
                elif e_type == "DATE_OF_BIRTH":
                    placeholder = "[PATIENT_DOB]"
                elif e_type in ["PHONE_NUMBER", "EMAIL_ADDRESS", "LOCATION"]:
                    placeholder = f"[PATIENT_{e_type}]"
                else:
                    placeholder = f"[REDACTED_{e_type}]"

                sanitized = sanitized[:entity["start"]] + placeholder + sanitized[entity["end"]:]
                result["mappings"][placeholder] = orig_val

            result["sanitized_text"] = sanitized
            return result

        # --- 5. REVERSIBLE PSEUDONYMIZATION / GENERAL ANONYMIZATION ---
        sanitized = text
        for entity in sorted(detected_entities, key=lambda x: x["start"], reverse=True):
            orig_val = entity["text"]
            e_type = entity["entity_type"]

            if e_type == "PERSON":
                fake_val = fake.first_name() if " " not in orig_val.strip() else fake.name()
            elif e_type == "EMAIL_ADDRESS":
                fake_val = fake.email()
            elif e_type == "PHONE_NUMBER":
                fake_val = fake.phone_number()
            elif e_type == "CREDIT_CARD":
                fake_val = fake.credit_card_number()
            elif e_type == "LOCATION":
                fake_val = fake.city()
            elif e_type in ["BANK_ACCOUNT", "US_BANK_NUMBER"]:
                fake_val = fake.bban()
            elif e_type == "API_KEY":
                fake_val = "YOUR_API_KEY_HERE"
            elif e_type == "PASSWORD_CREDENTIAL":
                fake_val = "YOUR_PASSWORD_HERE"
            else:
                fake_val = f"FAKE_{e_type}"

            sanitized = sanitized[:entity["start"]] + fake_val + sanitized[entity["end"]:]
            result["mappings"][fake_val] = orig_val

        result["sanitized_text"] = sanitized
        return result
