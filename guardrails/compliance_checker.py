"""
Compliance and business rule checking guardrails.
"""

import re
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from .base import BaseGuardrail, GuardrailResult, GuardrailSeverity


class ComplianceChecker(BaseGuardrail):
    """Base class for compliance checking guardrails."""
    
    def __init__(self, name: str, enabled: bool = True):
        super().__init__(name, enabled)


class BusinessRuleChecker(ComplianceChecker):
    """Checks content against custom business rules."""
    
    def __init__(self, rules: Optional[List[Dict[str, Any]]] = None, enabled: bool = True):
        super().__init__("business_rule_checker", enabled)
        self.rules = rules or []
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """Setup default business rules."""
        default_rules = [
            {
                "name": "no_competitor_mention",
                "description": "Prevent mention of competitor names",
                "pattern": r'\b(competitor1|competitor2|rival_company)\b',
                "severity": "medium",
                "action": "block"
            },
            {
                "name": "financial_advice_disclaimer",
                "description": "Require disclaimer for financial advice",
                "pattern": r'\b(specific investment advice|buy.*stock|sell.*stock|guaranteed.*profit)\b',
                "severity": "high", 
                "action": "require_disclaimer",
                "disclaimer": "This is not financial advice. Please consult with a qualified financial advisor."
            },
            {
                "name": "medical_advice_disclaimer", 
                "description": "Require disclaimer for medical advice",
                "pattern": r'\b(take.*medication|you have.*disease|diagnose.*with)\b',
                "severity": "high",
                "action": "require_disclaimer",
                "disclaimer": "This is not medical advice. Please consult with a qualified healthcare professional."
            }
        ]
        
        # Add default rules if no custom rules provided
        if not self.rules:
            self.rules = default_rules
    
    def add_rule(self, rule: Dict[str, Any]) -> None:
        """Add a custom business rule."""
        required_keys = ["name", "description", "pattern", "severity", "action"]
        if all(key in rule for key in required_keys):
            self.rules.append(rule)
        else:
            raise ValueError(f"Rule must contain all required keys: {required_keys}")
    
    async def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        """Check content against business rules."""
        violations = []
        triggered_rules = []
        
        for rule in self.rules:
            pattern = rule["pattern"]
            matches = re.findall(pattern, content, re.IGNORECASE)
            
            if matches:
                triggered_rules.append(rule)
                
                if rule["action"] == "block":
                    violations.append(f"Rule '{rule['name']}' violated: {rule['description']}")
                elif rule["action"] == "require_disclaimer":
                    disclaimer = rule.get("disclaimer", "")
                    if disclaimer and disclaimer not in content:
                        violations.append(f"Rule '{rule['name']}': Required disclaimer missing")
                elif rule["action"] == "flag":
                    violations.append(f"Rule '{rule['name']}' flagged: {rule['description']}")
        
        # Determine overall severity
        severity_levels = [rule["severity"] for rule in triggered_rules]
        max_severity = self._get_max_severity(severity_levels)
        
        passed = len(violations) == 0
        severity = max_severity if not passed else GuardrailSeverity.LOW
        
        message = f"Business rule check {'passed' if passed else 'failed'}"
        if not passed:
            message += f" ({len(violations)} violations)"
        
        return GuardrailResult(
            passed=passed,
            severity=severity,
            message=message,
            violations=violations,
            metadata={
                "triggered_rules": [rule["name"] for rule in triggered_rules],
                "total_rules_checked": len(self.rules)
            }
        )
    
    def _get_max_severity(self, severity_levels: List[str]) -> GuardrailSeverity:
        """Get the maximum severity from a list of severity strings."""
        severity_order = {
            "low": GuardrailSeverity.LOW,
            "medium": GuardrailSeverity.MEDIUM, 
            "high": GuardrailSeverity.HIGH,
            "critical": GuardrailSeverity.CRITICAL
        }
        
        if not severity_levels:
            return GuardrailSeverity.LOW
        
        max_severity_str = max(severity_levels, 
                              key=lambda x: list(severity_order.keys()).index(x))
        return severity_order[max_severity_str]


class DataGovernanceChecker(ComplianceChecker):
    """Checks for data governance and privacy compliance."""
    
    def __init__(self, enable_gdpr: bool = True, enable_ccpa: bool = True, enabled: bool = True):
        super().__init__("data_governance_checker", enabled)
        self.enable_gdpr = enable_gdpr
        self.enable_ccpa = enable_ccpa
        
        # Data categories that require special handling
        self.sensitive_data_patterns = {
            "personal_data": r'\b(personal data|personal information|PII)\b',
            "biometric_data": r'\b(biometric|fingerprint|facial recognition)\b',
            "health_data": r'\b(health data|medical records|health information)\b',
            "financial_data": r'\b(credit card|bank account|financial records)\b',
            "location_data": r'\b(location|GPS|geolocation|address)\b',
        }
    
    async def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        """Check content for data governance compliance."""
        violations = []
        detected_data_types = []
        
        # Check for sensitive data mentions
        for data_type, pattern in self.sensitive_data_patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                detected_data_types.append(data_type)
        
        # GDPR compliance checks
        if self.enable_gdpr and detected_data_types:
            violations.extend(self._check_gdpr_compliance(content, detected_data_types))
        
        # CCPA compliance checks
        if self.enable_ccpa and detected_data_types:
            violations.extend(self._check_ccpa_compliance(content, detected_data_types))
        
        # Check for proper consent language
        if detected_data_types and not self._has_consent_language(content):
            violations.append("Sensitive data mentioned without proper consent language")
        
        passed = len(violations) == 0
        severity = GuardrailSeverity.HIGH if not passed else GuardrailSeverity.LOW
        
        message = f"Data governance check {'passed' if passed else 'failed'}"
        if not passed:
            message += f" ({len(violations)} violations)"
        
        return GuardrailResult(
            passed=passed,
            severity=severity,
            message=message,
            violations=violations,
            metadata={
                "detected_data_types": detected_data_types,
                "gdpr_enabled": self.enable_gdpr,
                "ccpa_enabled": self.enable_ccpa
            }
        )
    
    def _check_gdpr_compliance(self, content: str, data_types: List[str]) -> List[str]:
        """Check GDPR compliance requirements."""
        violations = []
        
        # Check for required GDPR rights mentions
        gdpr_rights = [
            "right to access", "right to rectification", "right to erasure",
            "right to restrict processing", "right to data portability"
        ]
        
        mentions_rights = any(right in content.lower() for right in gdpr_rights)
        if not mentions_rights:
            violations.append("GDPR: No mention of data subject rights")
        
        # Check for lawful basis
        lawful_basis_keywords = ["consent", "contract", "legal obligation", "legitimate interest"]
        has_lawful_basis = any(keyword in content.lower() for keyword in lawful_basis_keywords)
        if not has_lawful_basis:
            violations.append("GDPR: No lawful basis for processing mentioned")
        
        return violations
    
    def _check_ccpa_compliance(self, content: str, data_types: List[str]) -> List[str]:
        """Check CCPA compliance requirements."""
        violations = []
        
        # Check for CCPA rights mentions
        ccpa_rights = ["right to know", "right to delete", "right to opt-out"]
        mentions_rights = any(right in content.lower() for right in ccpa_rights)
        
        if not mentions_rights:
            violations.append("CCPA: No mention of consumer rights")
        
        return violations
    
    def _has_consent_language(self, content: str) -> bool:
        """Check if content has appropriate consent language."""
        consent_phrases = [
            "with your consent", "you agree", "by proceeding", 
            "you acknowledge", "opt-in", "permission"
        ]
        return any(phrase in content.lower() for phrase in consent_phrases)


class IndustryComplianceChecker(ComplianceChecker):
    """Checks for industry-specific compliance (HIPAA, SOX, etc.)."""
    
    def __init__(self, industry: str = "general", enabled: bool = True):
        super().__init__(f"industry_compliance_checker_{industry}", enabled)
        self.industry = industry
        self.compliance_rules = self._get_industry_rules(industry)
    
    def _get_industry_rules(self, industry: str) -> Dict[str, Any]:
        """Get compliance rules for specific industry."""
        rules = {
            "healthcare": {
                "required_disclaimers": ["HIPAA", "medical advice"],
                "forbidden_patterns": [r'\b(cure|guaranteed|miracle)\b'],
                "required_patterns": [r'\b(consult.*healthcare professional)\b']
            },
            "financial": {
                "required_disclaimers": ["SEC", "financial advice", "investment risk"],
                "forbidden_patterns": [r'\b(guaranteed returns|risk-free)\b'],
                "required_patterns": [r'\b(past performance.*future results)\b']
            },
            "legal": {
                "required_disclaimers": ["legal advice", "attorney-client"],
                "forbidden_patterns": [r'\b(guaranteed outcome|sure win)\b'],
                "required_patterns": [r'\b(consult.*attorney)\b']
            },
            "general": {
                "required_disclaimers": [],
                "forbidden_patterns": [],
                "required_patterns": []
            }
        }
        
        return rules.get(industry, rules["general"])
    
    async def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        """Check content for industry-specific compliance."""
        violations = []
        
        # Check required disclaimers
        for disclaimer in self.compliance_rules.get("required_disclaimers", []):
            if disclaimer.lower() not in content.lower():
                violations.append(f"Missing required {self.industry} disclaimer: {disclaimer}")
        
        # Check forbidden patterns
        for pattern in self.compliance_rules.get("forbidden_patterns", []):
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(f"Forbidden {self.industry} content pattern found: {pattern}")
        
        # Check required patterns
        for pattern in self.compliance_rules.get("required_patterns", []):
            if not re.search(pattern, content, re.IGNORECASE):
                violations.append(f"Required {self.industry} pattern missing: {pattern}")
        
        passed = len(violations) == 0
        severity = GuardrailSeverity.HIGH if not passed else GuardrailSeverity.LOW
        
        message = f"{self.industry.title()} compliance check {'passed' if passed else 'failed'}"
        if not passed:
            message += f" ({len(violations)} violations)"
        
        return GuardrailResult(
            passed=passed,
            severity=severity,
            message=message,
            violations=violations,
            metadata={"industry": self.industry}
        )