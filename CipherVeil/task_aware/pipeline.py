"""
Task-Aware Privacy Pipeline for CipherVeil.
Orchestrates Detection -> Task Classification -> Privacy Policy -> Transformation -> Validation -> Review.
"""

from typing import Dict, Any, Optional

from .detection import TaskAwareDetectionEngine
from .classification import TaskClassifier
from .policy import PrivacyPolicyEngine
from .transformation import TaskAwareTransformer
from .validation import SanitizationValidator


class TaskAwarePipeline:
    """End-to-end task-aware privacy transformation pipeline."""

    def __init__(self):
        self.detection_engine = TaskAwareDetectionEngine()
        self.classifier = TaskClassifier()
        self.policy_engine = PrivacyPolicyEngine()
        self.transformer = TaskAwareTransformer()
        self.validator = SanitizationValidator()

    def process(self, prompt: str, url: str = "") -> Dict[str, Any]:
        """
        Execute the full pipeline on a user prompt.
        Returns detailed transparent decision breakdown and sanitized output.
        """
        if not prompt or not prompt.strip():
            return {
                "status": "empty",
                "original_text": prompt,
                "sanitized_text": prompt,
                "task_info": {"task_type": "EMPTY", "confidence": 1.0},
                "detected_entities": [],
                "can_answer_locally": False,
                "local_answer": None,
                "mappings": {},
                "validation": {"is_valid": True, "risk_score": 0.0}
            }

        # Step 1: Detect sensitive PII, technical credentials, secrets, financial, DOB
        detected_entities = self.detection_engine.detect(prompt)

        # Step 2: Classify the user's intended task
        task_info = self.classifier.classify(prompt, detected_entities)

        # Step 3: Determine task-specific privacy policy & strategy
        policy = self.policy_engine.evaluate(task_info, detected_entities)

        # Step 4: Execute Transformation or Local Computation
        transformation_result = self.transformer.transform(
            text=prompt,
            task_info=task_info,
            policy=policy,
            detected_entities=detected_entities
        )

        sanitized_text = transformation_result["sanitized_text"]

        # Step 5: Validate Sanitization
        validation_result = self.validator.validate(
            original_text=prompt,
            sanitized_text=sanitized_text,
            detected_entities=detected_entities,
            task_info=task_info
        )

        # Step 6: Transparency & User Review packaging
        requires_review = (
            any(e["sensitivity"] == "HIGH" for e in detected_entities)
            or not validation_result["is_valid"]
            or transformation_result.get("can_answer_locally", False)
        )

        return {
            "status": "success",
            "original_text": prompt,
            "sanitized_text": sanitized_text,
            "task_type": task_info["task_type"],
            "task_confidence": task_info["confidence"],
            "task_rationale": task_info["rationale"],
            "privacy_strategy": transformation_result["strategy"],
            "privacy_explanation": transformation_result["explanation"],
            "detected_entities": detected_entities,
            "detected_count": len(detected_entities),
            "can_answer_locally": transformation_result.get("can_answer_locally", False),
            "local_answer": transformation_result.get("local_answer"),
            "sanitized_representation": transformation_result.get("sanitized_representation"),
            "mappings": transformation_result.get("mappings", {}),
            "validation": validation_result,
            "requires_user_review": requires_review
        }
