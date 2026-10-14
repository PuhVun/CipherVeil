"""
Evaluation and Benchmark Suite for CipherVeil's Task-Aware Privacy Transformation Layer.
Runs automated test cases covering core tasks and evaluates privacy, utility, and local computation.
"""

from typing import List, Dict, Any
from ..pipeline import TaskAwarePipeline


class TaskAwareEvaluator:
    """Evaluates the Task-Aware Privacy Transformation pipeline against benchmark test cases."""

    BENCHMARK_CASES = [
        {
            "id": "TC-01",
            "name": "Card Brand Identification",
            "prompt": "My card number is 4111111111111111. Is this a Visa or Mastercard?",
            "expected_task": "CARD_BRAND_IDENTIFICATION",
            "expected_entities": ["CREDIT_CARD"],
            "must_not_contain": ["4111111111111111"],
            "expected_local_compute": True,
            "expected_brand": "Visa"
        },
        {
            "id": "TC-02",
            "name": "Age Calculation from DOB",
            "prompt": "I was born on 1990-05-14. How old am I?",
            "expected_task": "AGE_DATE_CALCULATION",
            "expected_entities": ["DATE_OF_BIRTH"],
            "must_not_contain": ["1990-05-14"],
            "expected_local_compute": True
        },
        {
            "id": "TC-03",
            "name": "Code Debugging with API Key",
            "prompt": "openai.api_key = 'sk-proj-abc12345678901234567890'. Why do I get invalid request?",
            "expected_task": "CODE_DEBUGGING",
            "expected_entities": ["API_KEY"],
            "must_not_contain": ["sk-proj-abc12345678901234567890"],
            "must_contain": ["openai.api_key", "invalid request"],
            "expected_local_compute": False
        },
        {
            "id": "TC-04",
            "name": "Bank Statement Financial Calculation",
            "prompt": "My account 987654321 had $4,500 deposited and $350 spent on food. What is the remaining balance?",
            "expected_task": "FINANCIAL_ANALYSIS",
            "expected_entities": ["BANK_ACCOUNT"],
            "must_not_contain": ["987654321"],
            "expected_local_compute": True
        },
        {
            "id": "TC-05",
            "name": "Medical Report Explanation",
            "prompt": "Patient John Doe, DOB 05/12/1982, presented with fasting blood sugar 160 mg/dL and HbA1c 7.5%. Explain these findings.",
            "expected_task": "MEDICAL_ANALYSIS",
            "expected_entities": ["PERSON", "DATE_OF_BIRTH"],
            "must_not_contain": ["John Doe", "05/12/1982"],
            "must_contain": ["blood sugar", "160 mg/dL", "HbA1c 7.5%"],
            "expected_local_compute": False
        },
        {
            "id": "TC-06",
            "name": "Document Generation with Personal Info",
            "prompt": "Write a cover letter for Sarah Connor applying for AI Engineer, email sconnor@skynet.com",
            "expected_task": "DOCUMENT_GENERATION",
            "expected_entities": ["PERSON", "EMAIL_ADDRESS"],
            "must_not_contain": ["Sarah Connor", "sconnor@skynet.com"],
            "must_contain": ["AI Engineer", "cover letter"],
            "expected_local_compute": False
        },
        {
            "id": "TC-07",
            "name": "General Chat with Personal Info",
            "prompt": "Hi, my name is saro and my email is saro67@mail.com",
            "expected_task": "GENERAL_QUERY",
            "expected_entities": ["PERSON", "EMAIL_ADDRESS"],
            "must_not_contain": ["saro67@mail.com"],
            "expected_local_compute": False
        }
    ]

    def __init__(self):
        self.pipeline = TaskAwarePipeline()

    def run_evaluations(self) -> Dict[str, Any]:
        """Run all test cases and compute accuracy, privacy, and utility scores."""
        results = []
        total_tests = len(self.BENCHMARK_CASES)
        classification_correct = 0
        detection_correct = 0
        zero_leakage_passes = 0
        utility_passes = 0
        local_compute_passes = 0

        for case in self.BENCHMARK_CASES:
            prompt = case["prompt"]
            out = self.pipeline.process(prompt)

            # 1. Classification check
            task_match = out["task_type"] == case["expected_task"]
            if task_match:
                classification_correct += 1

            # 2. Detection check
            found_entities = {e["entity_type"] for e in out["detected_entities"]}
            detection_match = all(exp in found_entities for exp in case["expected_entities"])
            if detection_match:
                detection_correct += 1

            # 3. Leakage check
            sanitized = out["sanitized_text"]
            leaks = [s for s in case.get("must_not_contain", []) if s in sanitized]
            leak_free = len(leaks) == 0 and out["validation"]["is_valid"]
            if leak_free:
                zero_leakage_passes += 1

            # 4. Utility / Context preservation check
            must_contain = case.get("must_contain", [])
            context_ok = all(s in sanitized for s in must_contain) and out["validation"]["context_preserved"]
            if context_ok:
                utility_passes += 1

            # 5. Local computation check
            expected_local = case.get("expected_local_compute", False)
            local_ok = True
            if expected_local:
                local_ok = out["can_answer_locally"] and out["local_answer"] is not None
                if case.get("expected_brand"):
                    local_ok = local_ok and case["expected_brand"] in str(out["local_answer"])
                if local_ok:
                    local_compute_passes += 1

            case_passed = task_match and detection_match and leak_free and context_ok and (not expected_local or local_ok)

            results.append({
                "id": case["id"],
                "name": case["name"],
                "passed": case_passed,
                "task_classified": out["task_type"],
                "task_expected": case["expected_task"],
                "task_confidence": out["task_confidence"],
                "detected_entities": [f"{e['entity_type']} ({e['text']})" for e in out["detected_entities"]],
                "privacy_strategy": out["privacy_strategy"],
                "can_answer_locally": out["can_answer_locally"],
                "local_answer_preview": out["local_answer"][:80] + "..." if out["local_answer"] else None,
                "sanitized_preview": sanitized[:80] + "..." if len(sanitized) > 80 else sanitized,
                "leaks": leaks,
                "risk_score": out["validation"]["risk_score"]
            })

        summary = {
            "total_test_cases": total_tests,
            "overall_tests_passed": sum(1 for r in results if r["passed"]),
            "pass_rate_percentage": round((sum(1 for r in results if r["passed"]) / total_tests) * 100, 1),
            "metrics": {
                "classification_accuracy": round((classification_correct / total_tests) * 100, 1),
                "detection_recall": round((detection_correct / total_tests) * 100, 1),
                "zero_leakage_rate": round((zero_leakage_passes / total_tests) * 100, 1),
                "task_utility_preservation": round((utility_passes / total_tests) * 100, 1),
                "local_computation_success_rate": round((local_compute_passes / 3) * 100, 1)
            },
            "test_cases": results
        }

        return summary


if __name__ == "__main__":
    evaluator = TaskAwareEvaluator()
    report = evaluator.run_evaluations()
    print("=" * 60)
    print("CIPHERVEIL TASK-AWARE PRIVACY EVALUATION REPORT")
    print("=" * 60)
    print(f"Total Test Cases: {report['total_test_cases']}")
    print(f"Tests Passed:     {report['overall_tests_passed']}/{report['total_test_cases']} ({report['pass_rate_percentage']}%)")
    print("\nMetrics:")
    for k, v in report['metrics'].items():
        print(f"  - {k.replace('_', ' ').title()}: {v}%")
    print("\nIndividual Results:")
    for t in report['test_cases']:
        status = "PASSED" if t['passed'] else "FAILED"
        print(f"[{status}] {t['id']}: {t['name']}")
        print(f"        Task: {t['task_classified']} | Strategy: {t['privacy_strategy']} | Local: {t['can_answer_locally']}")
        if t['local_answer_preview']:
            print(f"        Local Answer: {t['local_answer_preview']}")
        print(f"        Sanitized: {t['sanitized_preview']}")
        print()
