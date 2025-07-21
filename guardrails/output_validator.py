"""
Output validation guardrails for structure and format checking.
"""

import json
import re
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ValidationError
from .base import BaseGuardrail, GuardrailResult, GuardrailSeverity


class OutputValidator(BaseGuardrail):
    """Base class for output validation guardrails."""
    
    def __init__(self, name: str, enabled: bool = True):
        super().__init__(name, enabled)


class StructureValidator(OutputValidator):
    """Validates output structure against expected schemas."""
    
    def __init__(self, expected_schema: Optional[Dict[str, Any]] = None, enabled: bool = True):
        super().__init__("structure_validator", enabled)
        self.expected_schema = expected_schema
    
    async def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        """Check if content matches expected structure."""
        violations = []
        
        # Try to parse as JSON first
        try:
            parsed_content = json.loads(content)
            
            if self.expected_schema:
                violations.extend(self._validate_against_schema(parsed_content, self.expected_schema))
            
        except json.JSONDecodeError:
            # If not JSON, check for basic structure patterns
            violations.extend(self._validate_text_structure(content))
        
        passed = len(violations) == 0
        severity = GuardrailSeverity.MEDIUM if not passed else GuardrailSeverity.LOW
        
        message = f"Structure validation {'passed' if passed else 'failed'}"
        if not passed:
            message += f" ({len(violations)} violations)"
        
        return GuardrailResult(
            passed=passed,
            severity=severity,
            message=message,
            violations=violations,
            metadata={"has_schema": self.expected_schema is not None}
        )
    
    def _validate_against_schema(self, content: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
        """Validate content against a schema."""
        violations = []
        
        # Check required fields
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in content:
                violations.append(f"Missing required field: {field}")
        
        # Check field types
        properties = schema.get("properties", {})
        for field, field_schema in properties.items():
            if field in content:
                expected_type = field_schema.get("type")
                actual_value = content[field]
                
                if not self._check_type(actual_value, expected_type):
                    violations.append(f"Field '{field}' has wrong type: expected {expected_type}, got {type(actual_value).__name__}")
        
        return violations
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type."""
        type_mapping = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        
        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type:
            return isinstance(value, expected_python_type)
        
        return True
    
    def _validate_text_structure(self, content: str) -> List[str]:
        """Validate basic text structure."""
        violations = []
        
        # Check for empty content
        if not content.strip():
            violations.append("Content is empty")
        
        # Check for incomplete sentences
        if content.strip() and not content.strip().endswith(('.', '!', '?', ':')):
            violations.append("Content appears incomplete (no proper ending)")
        
        return violations


class FormatValidator(OutputValidator):
    """Validates output format and patterns."""
    
    def __init__(self, 
                 allowed_formats: Optional[List[str]] = None,
                 required_patterns: Optional[List[str]] = None,
                 forbidden_patterns: Optional[List[str]] = None,
                 enabled: bool = True):
        super().__init__("format_validator", enabled)
        self.allowed_formats = allowed_formats or ["text", "json", "markdown"]
        self.required_patterns = required_patterns or []
        self.forbidden_patterns = forbidden_patterns or []
    
    async def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        """Check content format."""
        violations = []
        detected_format = self._detect_format(content)
        
        # Check allowed formats
        if self.allowed_formats and detected_format not in self.allowed_formats:
            violations.append(f"Format '{detected_format}' not allowed. Allowed: {self.allowed_formats}")
        
        # Check required patterns
        for pattern in self.required_patterns:
            if not re.search(pattern, content, re.IGNORECASE):
                violations.append(f"Required pattern missing: {pattern}")
        
        # Check forbidden patterns
        for pattern in self.forbidden_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(f"Forbidden pattern found: {pattern}")
        
        passed = len(violations) == 0
        severity = GuardrailSeverity.MEDIUM if not passed else GuardrailSeverity.LOW
        
        message = f"Format validation {'passed' if passed else 'failed'}"
        if not passed:
            message += f" ({len(violations)} violations)"
        
        return GuardrailResult(
            passed=passed,
            severity=severity,
            message=message,
            violations=violations,
            metadata={"detected_format": detected_format}
        )
    
    def _detect_format(self, content: str) -> str:
        """Detect the format of content."""
        content_stripped = content.strip()
        
        # Check for JSON
        if content_stripped.startswith('{') and content_stripped.endswith('}'):
            try:
                json.loads(content_stripped)
                return "json"
            except json.JSONDecodeError:
                pass
        
        # Check for Markdown
        markdown_patterns = [
            r'^#{1,6}\s',  # Headers
            r'\*\*.*?\*\*',  # Bold
            r'\*.*?\*',  # Italic
            r'```',  # Code blocks
            r'\[.*?\]\(.*?\)',  # Links
        ]
        
        if any(re.search(pattern, content, re.MULTILINE) for pattern in markdown_patterns):
            return "markdown"
        
        # Check for HTML
        if re.search(r'<[^>]+>', content):
            return "html"
        
        # Default to text
        return "text"


class ResponseCompletenessValidator(OutputValidator):
    """Validates that responses are complete and coherent."""
    
    def __init__(self, min_length: int = 10, max_length: int = 5000, enabled: bool = True):
        super().__init__("completeness_validator", enabled)
        self.min_length = min_length
        self.max_length = max_length
    
    async def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        """Check response completeness."""
        violations = []
        content_length = len(content.strip())
        
        # Check length bounds
        if content_length < self.min_length:
            violations.append(f"Response too short: {content_length} < {self.min_length}")
        
        if content_length > self.max_length:
            violations.append(f"Response too long: {content_length} > {self.max_length}")
        
        # Check for truncated responses
        truncation_indicators = [
            "...",
            "[truncated]",
            "[continued]",
            "and more",
        ]
        
        content_lower = content.lower()
        for indicator in truncation_indicators:
            if indicator in content_lower:
                violations.append(f"Response appears truncated: contains '{indicator}'")
        
        # Check for incomplete code blocks
        if content.count("```") % 2 != 0:
            violations.append("Response contains unclosed code blocks")
        
        # Check for incomplete sentences (basic heuristic)
        sentences = content.split('.')
        if len(sentences) > 1:
            last_sentence = sentences[-1].strip()
            if last_sentence and len(last_sentence) > 50:  # Likely incomplete
                violations.append("Response may end with incomplete sentence")
        
        passed = len(violations) == 0
        severity = GuardrailSeverity.MEDIUM if not passed else GuardrailSeverity.LOW
        
        message = f"Completeness validation {'passed' if passed else 'failed'}"
        if not passed:
            message += f" ({len(violations)} violations)"
        
        return GuardrailResult(
            passed=passed,
            severity=severity,
            message=message,
            violations=violations,
            metadata={
                "content_length": content_length,
                "min_length": self.min_length,
                "max_length": self.max_length
            }
        )


class PydanticValidator(OutputValidator):
    """Validates output against Pydantic models."""
    
    def __init__(self, model_class: type[BaseModel], enabled: bool = True):
        super().__init__(f"pydantic_validator_{model_class.__name__}", enabled)
        self.model_class = model_class
    
    async def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        """Validate content against Pydantic model."""
        violations = []
        
        try:
            # Try to parse as JSON first
            if isinstance(content, str):
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    # If not JSON, treat as raw data
                    data = content
            else:
                data = content
            
            # Validate against model
            validated_data = self.model_class.model_validate(data)
            
        except ValidationError as e:
            for error in e.errors():
                field = ".".join(str(x) for x in error["loc"]) if error["loc"] else "root"
                violations.append(f"Validation error in '{field}': {error['msg']}")
        except Exception as e:
            violations.append(f"Unexpected validation error: {str(e)}")
        
        passed = len(violations) == 0
        severity = GuardrailSeverity.HIGH if not passed else GuardrailSeverity.LOW
        
        message = f"Pydantic validation {'passed' if passed else 'failed'}"
        if not passed:
            message += f" ({len(violations)} violations)"
        
        return GuardrailResult(
            passed=passed,
            severity=severity,
            message=message,
            violations=violations,
            metadata={"model_class": self.model_class.__name__}
        )