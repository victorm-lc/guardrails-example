"""
Basic usage examples for LangGraph guardrails.

This script demonstrates the simple guardrails agent - perfect for beginners!
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from simple_guardrails_agent import SimpleGuardrailAgent


def run_simple_agent_examples():
    """Run examples with the simple guardrails agent."""
    print("="*60)
    print("SIMPLE GUARDRAILS AGENT EXAMPLES")
    print("="*60)
    
    agent = SimpleGuardrailAgent()
    
    examples = [
        {
            "name": "Safe Query",
            "input": "What are the benefits of renewable energy?",
            "expected": "Should pass all guardrails"
        },
        {
            "name": "PII Detection", 
            "input": "My email is john.doe@example.com, can you help me?",
            "expected": "Should detect email and block"
        },
        {
            "name": "Toxic Content",
            "input": "I hate this stupid system!",
            "expected": "Should detect toxic keywords and block"
        },
        {
            "name": "Medical Advice",
            "input": "Should I take medicine for my headache?",
            "expected": "Should work but may need disclaimer in response"
        },
        {
            "name": "Empty Input",
            "input": "",
            "expected": "Should block empty input"
        },
        {
            "name": "Too Long",
            "input": "This is a very long message. " * 100,
            "expected": "Should block input that's too long"
        }
    ]
    
    for example in examples:
        print(f"\n--- {example['name']} ---")
        print(f"Input: {example['input'][:50]}{'...' if len(example['input']) > 50 else ''}")
        print(f"Expected: {example['expected']}")
        
        try:
            result = agent.run(example['input'])
            
            if result['success']:
                print("✅ SUCCESS")
                print(f"Response: {result['response'][:150]}...")
            else:
                print("❌ BLOCKED")
                print(f"Reason: {result['blocked_reason']}")
            
            print(f"Input Safe: {result['input_safe']} | Output Safe: {result['output_safe']}")
        
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Main function to run the simple examples."""
    print("LangGraph Guardrails - Simple Example")
    print("This demonstrates the basics of using guardrails with LangGraph")
    print("Perfect for beginners learning the concepts!")
    
    try:
        run_simple_agent_examples()
        
        print("\n" + "="*60)
        print("SIMPLE EXAMPLES COMPLETED")
        print("="*60)
        print("✅ All examples executed successfully!")
        print("\nWhat you learned:")
        print("- How to validate user input before processing")
        print("- How to check AI output for safety issues")
        print("- How to use LangGraph conditional edges for guardrails")
        print("- Simple pattern matching for content filtering")
        print("\nNext steps:")
        print("- Check out advanced_custom_agent.py for complex patterns")
        print("- Look at the guardrails/ folder for specialized validators")
        
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
    
    main()