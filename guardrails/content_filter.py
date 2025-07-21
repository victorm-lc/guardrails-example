"""
Content filtering guardrails for safety and compliance.
"""

import re
import os
from typing import Any, Dict, List, Optional, Set
from .base import BaseGuardrail, GuardrailResult, GuardrailSeverity


class ContentFilter(BaseGuardrail):
    """Base class for content filtering guardrails."""
    
    def __init__(self, name: str, enabled: bool = True):
        super().__init__(name, enabled)
        self.blocked_patterns: List[str] = []
        self.allowed_patterns: List[str] = []


class ToxicityFilter(ContentFilter):
    """Filter for toxic and harmful content."""
    
    def __init__(self, threshold: float = 0.7, enabled: bool = True):
        super().__init__("toxicity_filter", enabled)
        self.threshold = float(os.getenv("TOXICITY_THRESHOLD", threshold))
        
        # Basic toxic patterns (in production, use a proper toxicity detection model)
        self.toxic_patterns = [
            r'\b(hate|kill|die|stupid|idiot|moron)\b',
            r'\b(racist|sexist|homophobic)\b',
            r'\b(violence|violent|aggressive)\b',
        ]
        
    async def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        """Check content for toxicity."""
        violations = []
        content_lower = content.lower()
        
        for pattern in self.toxic_patterns:
            matches = re.findall(pattern, content_lower, re.IGNORECASE)
            if matches:
                violations.extend([f"Toxic language detected: '{match}'" for match in matches])
        
        # Simulate toxicity score (in production, use a real model)
        toxicity_score = len(violations) * 0.3
        
        passed = toxicity_score < self.threshold
        severity = GuardrailSeverity.HIGH if not passed else GuardrailSeverity.LOW
        
        message = f"Toxicity check {'passed' if passed else 'failed'}"
        if not passed:
            message += f" (score: {toxicity_score:.2f}, threshold: {self.threshold})"
        
        return GuardrailResult(
            passed=passed,
            severity=severity,
            message=message,
            violations=violations,
            metadata={"toxicity_score": toxicity_score, "threshold": self.threshold}
        )


class PIIFilter(ContentFilter):
    """Filter for Personally Identifiable Information (PII)."""
    
    def __init__(self, enabled: bool = True):
        super().__init__("pii_filter", enabled)
        self.pii_enabled = os.getenv("PII_DETECTION_ENABLED", "true").lower() == "true"
        
        # PII patterns
        self.pii_patterns = {
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phone": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
            "credit_card": r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        }
    
    async def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        """Check content for PII."""
        if not self.pii_enabled:
            return GuardrailResult(
                passed=True,
                severity=GuardrailSeverity.LOW,
                message="PII detection disabled",
                violations=[],
                metadata={"pii_detection_enabled": False}
            )
        
        violations = []
        detected_pii = {}
        
        for pii_type, pattern in self.pii_patterns.items():
            matches = re.findall(pattern, content)
            if matches:
                detected_pii[pii_type] = len(matches)
                violations.append(f"{pii_type.upper()} detected: {len(matches)} instances")
        
        passed = len(violations) == 0
        severity = GuardrailSeverity.CRITICAL if not passed else GuardrailSeverity.LOW
        
        message = f"PII check {'passed' if passed else 'failed'}"
        if not passed:
            message += f" ({len(violations)} types of PII detected)"
        
        return GuardrailResult(
            passed=passed,
            severity=severity,
            message=message,
            violations=violations,
            metadata={"detected_pii": detected_pii}
        )


class ProfanityFilter(ContentFilter):
    """Filter for profanity and inappropriate language."""
    
    def __init__(self, strict_mode: bool = False, enabled: bool = True):
        super().__init__("profanity_filter", enabled)
        self.strict_mode = os.getenv("CONTENT_FILTER_STRICT_MODE", str(strict_mode)).lower() == "true"
        
        # Basic profanity patterns (extend this list as needed)
        self.profanity_patterns = [
            r'\b(damn|hell|crap)\b',  # mild
            r'\b(shit|fuck|bitch)\b',  # strong
        ]
        
        if self.strict_mode:
            self.profanity_patterns.extend([
                r'\b(stupid|dumb|idiot)\b',  # additional in strict mode
            ])
    
    async def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        """Check content for profanity."""
        violations = []
        content_lower = content.lower()
        
        for pattern in self.profanity_patterns:
            matches = re.findall(pattern, content_lower, re.IGNORECASE)
            if matches:
                violations.extend([f"Profanity detected: '{match}'" for match in matches])
        
        passed = len(violations) == 0
        severity = GuardrailSeverity.MEDIUM if not passed else GuardrailSeverity.LOW
        
        message = f"Profanity check {'passed' if passed else 'failed'}"
        if not passed:
            message += f" ({len(violations)} violations)"
        
        return GuardrailResult(
            passed=passed,
            severity=severity,
            message=message,
            violations=violations,
            metadata={"strict_mode": self.strict_mode}
        )


class ContentLengthFilter(ContentFilter):
    """Filter for content length restrictions."""
    
    def __init__(self, max_length: int = 10000, min_length: int = 1, enabled: bool = True):
        super().__init__("content_length_filter", enabled)
        self.max_length = max_length
        self.min_length = min_length
    
    async def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        """Check content length."""
        content_length = len(content)
        violations = []
        
        if content_length > self.max_length:
            violations.append(f"Content too long: {content_length} > {self.max_length}")
        
        if content_length < self.min_length:
            violations.append(f"Content too short: {content_length} < {self.min_length}")
        
        passed = len(violations) == 0
        severity = GuardrailSeverity.MEDIUM if not passed else GuardrailSeverity.LOW
        
        message = f"Length check {'passed' if passed else 'failed'}"
        if not passed:
            message += f" (length: {content_length})"
        
        return GuardrailResult(
            passed=passed,
            severity=severity,
            message=message,
            violations=violations,
            metadata={
                "content_length": content_length,
                "max_length": self.max_length,
                "min_length": self.min_length
            }
        )