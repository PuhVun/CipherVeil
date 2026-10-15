"""
Local Solvers Engine for Task-Aware Privacy in CipherVeil.
Executes computations locally on the user's machine for sensitive tasks
(Credit card brand identification, Age/Date calculation, Financial totals)
without transmitting sensitive data to external LLMs.
"""

from datetime import datetime, date
import re
from typing import Dict, Any, Optional


class CreditCardLocalSolver:
    """Computes card brand, issuer, and Luhn validity 100% locally."""

    @staticmethod
    def luhn_checksum(card_number_str: str) -> bool:
        digits = [int(c) for c in re.sub(r'\D', '', card_number_str)]
        if len(digits) < 13:
            return False
        total = 0
        reverse_digits = digits[::-1]
        for i, digit in enumerate(reverse_digits):
            if i % 2 == 1:
                doubled = digit * 2
                total += doubled - 9 if doubled > 9 else doubled
            else:
                total += digit
        return total % 10 == 0

    @staticmethod
    def identify_brand(card_number_str: str) -> str:
        clean = re.sub(r'\D', '', card_number_str)
        if not clean:
            return "Unknown"

        # Visa: starts with 4
        if clean.startswith('4'):
            return "Visa"
        # Mastercard: 51-55 or 2221-2720
        if 51 <= int(clean[:2]) <= 55 or (len(clean) >= 4 and 2221 <= int(clean[:4]) <= 2720):
            return "Mastercard"
        # Amex: 34 or 37
        if clean[:2] in ['34', '37']:
            return "American Express (Amex)"
        # Discover: 6011, 65, 644-649
        if clean.startswith('6011') or clean.startswith('65') or (len(clean) >= 3 and 644 <= int(clean[:3]) <= 649):
            return "Discover"
        # Diners Club: 300-305, 36, 38
        if clean[:2] in ['36', '38'] or (len(clean) >= 3 and 300 <= int(clean[:3]) <= 305):
            return "Diners Club"
        # JCB: 3528-3589
        if len(clean) >= 4 and 3528 <= int(clean[:4]) <= 3589:
            return "JCB"
        return "Unknown Card Network"

    @classmethod
    def solve(cls, text: str, card_number_str: str) -> Dict[str, Any]:
        clean = re.sub(r'\D', '', card_number_str)
        brand = cls.identify_brand(clean)
        is_luhn_valid = cls.luhn_checksum(clean)
        luhn_str = "passes Luhn validity check" if is_luhn_valid else "fails Luhn checksum"
        bin_prefix = clean[:6] if len(clean) >= 6 else clean

        answer = (
            f"Your card (prefix: **{bin_prefix}**) is associated with the **{brand}** payment network ({luhn_str}).\n\n"
            f"[CipherVeil Privacy Shield: This task was answered 100% locally. "
            f"Your full card number was never transmitted to external AI servers.]"
        )

        return {
            "can_solve_locally": True,
            "brand": brand,
            "is_valid": is_luhn_valid,
            "bin_prefix": bin_prefix,
            "answer": answer
        }


class AgeLocalSolver:
    """Calculates age directly from a Date of Birth string locally."""

    MONTH_MAP = {
        'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
        'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
        'aug': 8, 'august': 8, 'sep': 9, 'september': 9, 'oct': 10, 'october': 10,
        'nov': 11, 'november': 11, 'dec': 12, 'december': 12
    }

    @classmethod
    def parse_dob(cls, dob_str: str) -> Optional[date]:
        dob_str = dob_str.strip().lower()
        # 1. YYYY-MM-DD
        m = re.search(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', dob_str)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass

        # 2. MM/DD/YYYY or DD/MM/YYYY
        m = re.search(r'(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})', dob_str)
        if m:
            v1, v2, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            # Assume MM/DD/YYYY if v1 <= 12, else DD/MM/YYYY
            try:
                return date(year, v1, v2)
            except ValueError:
                try:
                    return date(year, v2, v1)
                except ValueError:
                    pass

        # 3. Month DD, YYYY (e.g., "May 14, 1990" or "14th May 1990")
        for month_name, month_num in cls.MONTH_MAP.items():
            if month_name in dob_str:
                day_m = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\b', dob_str)
                year_m = re.search(r'\b(\d{4})\b', dob_str)
                if day_m and year_m:
                    try:
                        return date(int(year_m.group(1)), month_num, int(day_m.group(1)))
                    except ValueError:
                        pass
        return None

    @classmethod
    def solve(cls, text: str, dob_str: str, reference_date: Optional[date] = None) -> Dict[str, Any]:
        ref = reference_date or date.today()
        dob = cls.parse_dob(dob_str)
        if not dob:
            return {"can_solve_locally": False, "answer": None}

        # Calculate exact age
        age = ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))

        answer = (
            f"Based on the birth date **{dob.strftime('%B %d, %Y')}**, your current age is **{age} years old** "
            f"(as of {ref.strftime('%B %Y')}).\n\n"
            f"🛡️ *Security Notice: This calculation was completed 100% locally on your device by CipherVeil. "
            f"Your date of birth was never sent to external servers.*"
        )

        return {
            "can_solve_locally": True,
            "age_years": age,
            "dob_parsed": dob.isoformat(),
            "answer": answer
        }


class FinancialLocalSolver:
    """Performs arithmetic calculations locally on amounts extracted from statements."""

    @classmethod
    def solve(cls, text: str) -> Dict[str, Any]:
        # Extract dollar amounts: e.g. "$4,500 deposited and $350 spent" or "deposited $4,500"
        dep_pattern = re.compile(
            r'(?:\$?([\d,]+(?:\.\d{2})?)\s*(?:deposit(?:ed)?|added|credited|income)|'
            r'(?:deposit(?:ed)?|added|credited|income)\s*(?:of)?\s*\$?([\d,]+(?:\.\d{2})?))',
            re.IGNORECASE
        )
        exp_pattern = re.compile(
            r'(?:\$?([\d,]+(?:\.\d{2})?)\s*(?:spent|withdrew|withdrawn|expense|debited)|'
            r'(?:spent|withdrew|withdrawn|expense|debited)\s*(?:of)?\s*\$?([\d,]+(?:\.\d{2})?))',
            re.IGNORECASE
        )

        deposits = [m[0] or m[1] for m in dep_pattern.findall(text)]
        expenses = [m[0] or m[1] for m in exp_pattern.findall(text)]

        if not deposits and not expenses:
            return {"can_solve_locally": False, "answer": None}

        def clean_sum(vals):
            return sum(float(v.replace(',', '')) for v in vals)

        dep_sum = clean_sum(deposits)
        exp_sum = clean_sum(expenses)
        net_balance = dep_sum - exp_sum

        answer = (
            f"**Financial Calculation Summary (Computed Locally):**\n"
            f"- Total Deposits/Credits: **${dep_sum:,.2f}**\n"
            f"- Total Expenses/Debits: **${exp_sum:,.2f}**\n"
            f"- Remaining Net Balance: **${net_balance:,.2f}**\n\n"
            f"🛡️ *Security Notice: Solved locally by CipherVeil without exposing account numbers or financial figures.*"
        )

        return {
            "can_solve_locally": True,
            "deposits_total": dep_sum,
            "expenses_total": exp_sum,
            "net_balance": net_balance,
            "answer": answer
        }
