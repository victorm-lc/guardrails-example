"""
Industry-specific guardrails examples.

This demonstrates how to configure guardrails for different industries
like healthcare, financial services, and legal.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from guardrails import (
    GuardrailManager, IndustryComplianceChecker, DataGovernanceChecker,
    BusinessRuleChecker, ToxicityFilter, ResponseCompletenessValidator
)


class IndustryGuardrailsDemo:
    """Demonstrates industry-specific guardrail configurations."""
    
    def __init__(self):
        self.industries = {
            "healthcare": self._setup_healthcare_guardrails(),
            "financial": self._setup_financial_guardrails(),
            "legal": self._setup_legal_guardrails(),
            "general": self._setup_general_guardrails()
        }
    
    def _setup_healthcare_guardrails(self) -> GuardrailManager:
        """Setup guardrails for healthcare industry."""
        manager = GuardrailManager()
        
        # Industry-specific compliance
        manager.add_guardrail(IndustryComplianceChecker(industry="healthcare"))
        
        # Data governance with HIPAA focus
        manager.add_guardrail(DataGovernanceChecker(enable_gdpr=False, enable_ccpa=True))
        
        # Business rules for healthcare
        healthcare_rules = [
            {
                "name": "medical_advice_disclaimer",
                "description": "Require medical disclaimer",
                "pattern": r'\b(diagnose|treatment|medication|prescription|symptoms|cure)\b',
                "severity": "high",
                "action": "require_disclaimer",
                "disclaimer": "This is not medical advice. Please consult with a qualified healthcare professional."
            },
            {
                "name": "hipaa_compliance",
                "description": "Prevent sharing of protected health information",
                "pattern": r'\b(patient|medical record|health information|diagnosis)\b',
                "severity": "critical",
                "action": "flag"
            }
        ]
        
        business_checker = BusinessRuleChecker()
        for rule in healthcare_rules:
            business_checker.add_rule(rule)
        manager.add_guardrail(business_checker)
        
        # Standard content filters
        manager.add_guardrail(ToxicityFilter(threshold=0.5))  # Stricter for healthcare
        manager.add_guardrail(ResponseCompletenessValidator())
        
        return manager
    
    def _setup_financial_guardrails(self) -> GuardrailManager:
        """Setup guardrails for financial services."""
        manager = GuardrailManager()
        
        # Industry-specific compliance
        manager.add_guardrail(IndustryComplianceChecker(industry="financial"))
        
        # Data governance
        manager.add_guardrail(DataGovernanceChecker())
        
        # Financial services business rules
        financial_rules = [
            {
                "name": "investment_advice_disclaimer",
                "description": "Require investment disclaimer",
                "pattern": r'\b(invest|investment|stock|bond|portfolio|trading|financial advice)\b',
                "severity": "high",
                "action": "require_disclaimer",
                "disclaimer": "This is not financial advice. Past performance does not guarantee future results. Please consult with a qualified financial advisor."
            },
            {
                "name": "no_guarantees",
                "description": "Prevent guaranteed return promises",
                "pattern": r'\b(guaranteed|promise|sure|certain).*\b(profit|return|gain)\b',
                "severity": "critical",
                "action": "block"
            },
            {
                "name": "risk_disclosure",
                "description": "Require risk disclosure",
                "pattern": r'\b(loan|credit|mortgage|insurance)\b',
                "severity": "medium",
                "action": "flag"
            }
        ]
        
        business_checker = BusinessRuleChecker()
        for rule in financial_rules:
            business_checker.add_rule(rule)
        manager.add_guardrail(business_checker)
        
        manager.add_guardrail(ToxicityFilter(threshold=0.6))
        manager.add_guardrail(ResponseCompletenessValidator())
        
        return manager
    
    def _setup_legal_guardrails(self) -> GuardrailManager:
        """Setup guardrails for legal services."""
        manager = GuardrailManager()
        
        # Industry-specific compliance
        manager.add_guardrail(IndustryComplianceChecker(industry="legal"))
        
        # Data governance
        manager.add_guardrail(DataGovernanceChecker())
        
        # Legal services business rules
        legal_rules = [
            {
                "name": "legal_advice_disclaimer",
                "description": "Require legal disclaimer",
                "pattern": r'\b(legal advice|lawsuit|contract|attorney|lawyer|court)\b',
                "severity": "high",
                "action": "require_disclaimer",
                "disclaimer": "This is not legal advice. Please consult with a qualified attorney."
            },
            {
                "name": "attorney_client_privilege",
                "description": "Protect attorney-client communications",
                "pattern": r'\b(privileged|confidential|attorney-client)\b',
                "severity": "critical",
                "action": "flag"
            },
            {
                "name": "no_outcome_guarantees",
                "description": "Prevent guaranteed legal outcomes",
                "pattern": r'\b(guarantee|promise|sure).*\b(win|victory|success)\b',
                "severity": "high",
                "action": "block"
            }
        ]
        
        business_checker = BusinessRuleChecker()
        for rule in legal_rules:
            business_checker.add_rule(rule)
        manager.add_guardrail(business_checker)
        
        manager.add_guardrail(ToxicityFilter(threshold=0.7))
        manager.add_guardrail(ResponseCompletenessValidator())
        
        return manager
    
    def _setup_general_guardrails(self) -> GuardrailManager:
        """Setup general-purpose guardrails."""
        manager = GuardrailManager()
        
        manager.add_guardrail(IndustryComplianceChecker(industry="general"))
        manager.add_guardrail(DataGovernanceChecker())
        manager.add_guardrail(BusinessRuleChecker())
        manager.add_guardrail(ToxicityFilter())
        manager.add_guardrail(ResponseCompletenessValidator())
        
        return manager
    
    async def test_industry_specific_queries(self):
        """Test queries specific to different industries."""
        
        test_cases = {
            "healthcare": [
                "What medication should I take for my headache?",
                "Can you diagnose my symptoms?",
                "What are the treatment options for diabetes?",
                "I have patient John's medical records here"
            ],
            "financial": [
                "Should I invest in Bitcoin right now?",
                "I guarantee you'll make 50% returns with this strategy",
                "What's the best loan for my situation?",
                "Give me specific stock picks for tomorrow"
            ],
            "legal": [
                "Should I sue my employer?",
                "Can you write a contract for me?",
                "I guarantee we'll win this case",
                "This is privileged attorney-client communication"
            ],
            "general": [
                "What's the weather today?",
                "How do I cook pasta?",
                "What's 2+2?",
                "Tell me about artificial intelligence"
            ]
        }
        
        for industry, queries in test_cases.items():
            print(f"\n{'='*60}")
            print(f"TESTING {industry.upper()} INDUSTRY GUARDRAILS")
            print(f"{'='*60}")
            
            manager = self.industries[industry]
            
            for i, query in enumerate(queries, 1):
                print(f"\n--- Test {i}: {query} ---")
                
                try:
                    results = await manager.check_all(
                        query,
                        context={"industry": industry, "test": True}
                    )
                    
                    # Summary
                    passed = sum(1 for r in results if r.passed)
                    total = len(results)
                    print(f"Guardrails: {passed}/{total} passed")
                    
                    # Show violations
                    violations = [r for r in results if not r.passed]
                    if violations:
                        print("Violations:")
                        for violation in violations:
                            print(f"  ❌ {violation.severity.value.upper()}: {violation.message}")
                            for v in violation.violations:
                                print(f"     - {v}")
                    else:
                        print("✅ All guardrails passed")
                
                except Exception as e:
                    print(f"Error testing query: {e}")
    
    async def compare_industry_responses(self):
        """Compare how the same query is handled across industries."""
        print(f"\n{'='*60}")
        print("CROSS-INDUSTRY COMPARISON")
        print(f"{'='*60}")
        
        # Test query that might trigger different rules in different industries
        test_query = "I need advice about my investment in healthcare stocks and legal issues"
        
        print(f"Query: {test_query}")
        print()
        
        for industry in ["healthcare", "financial", "legal", "general"]:
            print(f"--- {industry.upper()} INDUSTRY ---")
            
            manager = self.industries[industry]
            results = await manager.check_all(
                test_query,
                context={"industry": industry}
            )
            
            violations = [r for r in results if not r.passed]
            if violations:
                print(f"❌ {len(violations)} violations detected:")
                for violation in violations:
                    print(f"  • {violation.message}")
            else:
                print("✅ No violations detected")
            print()


async def main():
    """Run industry-specific guardrails demonstration."""
    print("LangGraph Guardrails - Industry-Specific Examples")
    print("This demonstrates how to configure guardrails for different industries")
    
    demo = IndustryGuardrailsDemo()
    
    try:
        await demo.test_industry_specific_queries()
        await demo.compare_industry_responses()
        
        print(f"\n{'='*60}")
        print("INDUSTRY DEMOS COMPLETED")
        print(f"{'='*60}")
        print("✅ Industry-specific guardrails demonstration completed!")
        print("\nKey insights:")
        print("- Healthcare: Strict medical advice disclaimers and HIPAA compliance")
        print("- Financial: Investment disclaimers and guaranteed return prevention")
        print("- Legal: Legal advice disclaimers and outcome guarantee prevention")
        print("- Different industries require different compliance approaches")
        print("- Guardrails can be customized with industry-specific business rules")
        
    except Exception as e:
        print(f"Error running industry demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())