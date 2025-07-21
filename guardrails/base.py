"""
Base classes for guardrails implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum


class GuardrailSeverity(Enum):
    """Severity levels for guardrail violations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class GuardrailResult:
    """Result of a guardrail check."""
    passed: bool
    severity: GuardrailSeverity
    message: str
    violations: List[str]
    metadata: Dict[str, Any]


class BaseGuardrail(ABC):
    """Base class for all guardrails."""
    
    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled
    
    @abstractmethod
    async def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        """
        Check content against the guardrail rules.
        
        Args:
            content: The content to check
            context: Optional context information
            
        Returns:
            GuardrailResult with the check results
        """
        pass
    
    def is_enabled(self) -> bool:
        """Check if this guardrail is enabled."""
        return self.enabled
    
    def enable(self) -> None:
        """Enable this guardrail."""
        self.enabled = True
    
    def disable(self) -> None:
        """Disable this guardrail."""
        self.enabled = False


class GuardrailManager:
    """Manages multiple guardrails and executes them."""
    
    def __init__(self):
        self.guardrails: List[BaseGuardrail] = []
    
    def add_guardrail(self, guardrail: BaseGuardrail) -> None:
        """Add a guardrail to the manager."""
        self.guardrails.append(guardrail)
    
    def remove_guardrail(self, name: str) -> bool:
        """Remove a guardrail by name."""
        for i, guardrail in enumerate(self.guardrails):
            if guardrail.name == name:
                del self.guardrails[i]
                return True
        return False
    
    async def check_all(
        self, 
        content: str, 
        context: Optional[Dict[str, Any]] = None,
        fail_fast: bool = False
    ) -> List[GuardrailResult]:
        """
        Run all enabled guardrails on the content.
        
        Args:
            content: The content to check
            context: Optional context information
            fail_fast: Stop on first failure if True
            
        Returns:
            List of GuardrailResult objects
        """
        results = []
        
        for guardrail in self.guardrails:
            if not guardrail.is_enabled():
                continue
                
            result = await guardrail.check(content, context)
            results.append(result)
            
            if fail_fast and not result.passed:
                break
        
        return results
    
    def has_violations(self, results: List[GuardrailResult]) -> bool:
        """Check if any guardrail results contain violations."""
        return any(not result.passed for result in results)
    
    def get_critical_violations(self, results: List[GuardrailResult]) -> List[GuardrailResult]:
        """Get all critical violations from results."""
        return [
            result for result in results 
            if not result.passed and result.severity == GuardrailSeverity.CRITICAL
        ]