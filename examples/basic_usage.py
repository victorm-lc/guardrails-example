"""
Basic usage examples for LangGraph guardrails.

This script demonstrates simple usage patterns for both custom and prebuilt agents
with guardrails integrated.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from custom_agent import CustomGuardrailAgent
from prebuilt_agent import PrebuiltGuardrailAgent


async def run_custom_agent_examples():
    """Run examples with the custom agent implementation."""
    print("="*60)
    print("CUSTOM AGENT EXAMPLES")
    print("="*60)
    
    agent = CustomGuardrailAgent()
    
    examples = [
        {
            "name": "Safe Query",
            "input": "What are the benefits of renewable energy?",
            "expected": "Should pass all guardrails"
        },
        {
            "name": "PII Detection",
            "input": "My email is john.doe@example.com and my phone is 555-123-4567. Can you help me?",
            "expected": "Should detect PII but not necessarily block"
        },
        {
            "name": "Toxic Content",
            "input": "I hate this stupid system and everyone who uses it!",
            "expected": "Should be flagged for toxicity"
        },
        {
            "name": "Business Rule Trigger",
            "input": "Can you give me specific investment advice for buying stocks?",
            "expected": "Should trigger business rule requiring disclaimer"
        }
    ]
    
    for example in examples:
        print(f"\n--- {example['name']} ---")
        print(f"Input: {example['input']}")
        print(f"Expected: {example['expected']}")
        
        try:
            result = await agent.run(example['input'])
            
            print(f"Success: {result['success']}")
            print(f"Final Step: {result['current_step']}")
            
            if result['success']:
                print(f"Response: {result['response'][:100]}...")
            
            # Show guardrail results
            violations_count = sum(1 for r in result['guardrail_results'] if not r['passed'])
            print(f"Guardrails: {len(result['guardrail_results']) - violations_count}/{len(result['guardrail_results'])} passed")
            
            for gr in result['guardrail_results']:
                if not gr['passed']:
                    print(f"  ❌ [{gr['step']}] {gr['message']}")
                    for violation in gr['violations']:
                        print(f"     - {violation}")
        
        except Exception as e:
            print(f"Error: {e}")


async def run_prebuilt_agent_examples():
    """Run examples with the prebuilt agent implementation."""
    print("\n" + "="*60)
    print("PREBUILT AGENT EXAMPLES")
    print("="*60)
    
    agent = PrebuiltGuardrailAgent()
    
    examples = [
        {
            "name": "Tool Usage - Weather",
            "input": "What's the weather like in New York?",
            "expected": "Should use weather tool and pass guardrails"
        },
        {
            "name": "Tool Usage - Calculator", 
            "input": "Calculate 25 * 13 + 7",
            "expected": "Should use calculator tool"
        },
        {
            "name": "PII in Query",
            "input": "Search for information about user@company.com",
            "expected": "Should detect PII in input"
        },
        {
            "name": "Profanity Filter",
            "input": "This damn calculator doesn't work properly",
            "expected": "Should detect mild profanity"
        }
    ]
    
    for example in examples:
        print(f"\n--- {example['name']} ---")
        print(f"Input: {example['input']}")
        print(f"Expected: {example['expected']}")
        
        try:
            result = await agent.run(example['input'])
            
            print(f"Success: {result['success']}")
            print(f"Blocked: {result['blocked']}")
            
            if result['success'] and result['response']:
                print(f"Response: {result['response'][:150]}...")
            
            # Show guardrail summary
            summary = agent.get_guardrail_summary(result)
            print(f"Guardrail Summary:\n{summary}")
        
        except Exception as e:
            print(f"Error: {e}")


async def run_guardrails_stress_test():
    """Test guardrails with challenging inputs."""
    print("\n" + "="*60)
    print("GUARDRAILS STRESS TEST")
    print("="*60)
    
    # Use prebuilt agent for stress test
    agent = PrebuiltGuardrailAgent()
    
    stress_tests = [
        {
            "name": "Multiple PII Types",
            "input": "My name is John Smith, email john@test.com, phone 555-1234, SSN 123-45-6789",
            "expected": "Should detect multiple PII types"
        },
        {
            "name": "Mixed Content",
            "input": "I hate this system! My email is test@example.com. Give me financial advice now!",
            "expected": "Should trigger multiple guardrails"
        },
        {
            "name": "Very Long Input",
            "input": "This is a very long query. " * 100,
            "expected": "Should handle length validation"
        },
        {
            "name": "Empty Input",
            "input": "",
            "expected": "Should handle empty input gracefully"
        }
    ]
    
    for test in stress_tests:
        print(f"\n--- {test['name']} ---")
        print(f"Input Length: {len(test['input'])} chars")
        print(f"Expected: {test['expected']}")
        
        try:
            result = await agent.run(test['input'])
            
            print(f"Success: {result['success']}")
            print(f"Blocked: {result['blocked']}")
            
            # Count violations
            input_violations = sum(1 for r in result['input_guardrail_results'] if not r.get('passed', True))
            output_violations = sum(1 for r in result['output_guardrail_results'] if not r.get('passed', True))
            
            print(f"Input Violations: {input_violations}")
            print(f"Output Violations: {output_violations}")
            
            # Show first few violations
            all_results = result['input_guardrail_results'] + result['output_guardrail_results']
            for gr in all_results[:3]:  # Show first 3 violations
                if isinstance(gr, dict) and not gr.get('passed', True):
                    print(f"  ❌ {gr.get('message', 'Unknown violation')}")
        
        except Exception as e:
            print(f"Error: {e}")


async def main():
    """Main function to run all examples."""
    print("LangGraph Guardrails - Basic Usage Examples")
    print("This demonstrates how to use guardrails with LangGraph agents")
    
    try:
        await run_custom_agent_examples()
        await run_prebuilt_agent_examples()
        await run_guardrails_stress_test()
        
        print("\n" + "="*60)
        print("EXAMPLES COMPLETED")
        print("="*60)
        print("✅ All examples executed successfully!")
        print("\nKey takeaways:")
        print("- Custom agents provide fine-grained control over guardrail placement")
        print("- Prebuilt agents offer easy integration via hooks")
        print("- Guardrails can detect various types of harmful content")
        print("- Multiple guardrails can work together for comprehensive protection")
        
    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Check for required environment variables
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not found in environment variables")
        print("Please set your OpenAI API key in .env file or environment")
        sys.exit(1)
    
    asyncio.run(main())