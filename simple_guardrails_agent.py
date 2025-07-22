"""
Simple LangGraph Guardrails Example

This example demonstrates the basics of adding safety guardrails to a LangGraph agent.
No complex classes or abstractions - just simple functions and clear patterns.

Perfect for learning how guardrails work in LangGraph!
"""

import os
import re
from typing import TypedDict, List
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END

load_dotenv()


class AgentState(TypedDict):
    """Simple state - just messages and validation results."""
    messages: List
    input_safe: bool
    output_safe: bool
    blocked_reason: str


def check_input_safety(text: str) -> tuple[bool, str]:
    """Simple input validation - checks for basic safety issues."""
    if not text or len(text.strip()) == 0:
        return False, "Empty input not allowed"
    
    if len(text) > 1000:
        return False, "Input too long (max 1000 characters)"
    
    # Simple toxicity check using keywords (in production, use a real toxicity API)
    toxic_words = ["hate", "kill", "destroy", "stupid", "idiot"]
    text_lower = text.lower()
    for word in toxic_words:
        if word in text_lower:
            return False, f"Potentially toxic content detected: '{word}'"
    
    # Simple PII detection (email patterns)
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    if re.search(email_pattern, text):
        return False, "Personal email detected - please remove sensitive information"
    
    return True, "Input looks safe"


def check_output_safety(text: str) -> tuple[bool, str]:
    """Simple output validation - ensures AI responses are appropriate."""
    if not text or len(text.strip()) < 10:
        return False, "Response too short or empty"
    
    # Check for AI giving medical/legal advice without disclaimers
    advice_keywords = ["diagnose", "treatment", "legal advice", "sue", "lawsuit"]
    text_lower = text.lower()
    
    for keyword in advice_keywords:
        if keyword in text_lower:
            # Check if disclaimer is present
            disclaimer_words = ["disclaimer", "not medical advice", "consult", "professional"]
            has_disclaimer = any(disc in text_lower for disc in disclaimer_words)
            if not has_disclaimer:
                return False, f"Response contains '{keyword}' but lacks proper disclaimer"
    
    return True, "Output looks safe"


def validate_input(state: AgentState) -> AgentState:
    """Validate user input before processing."""
    # Get the user's message
    user_message = state["messages"][-1].content
    
    # Check if input is safe
    is_safe, reason = check_input_safety(user_message)
    state["input_safe"] = is_safe
    
    if not is_safe:
        state["blocked_reason"] = f"Input blocked: {reason}"
    
    return state


def generate_response(state: AgentState) -> AgentState:
    """Generate AI response with safety guidelines."""
    # Create LLM with safety instructions
    llm = ChatOpenAI(
        model="gpt-4o-mini", 
        temperature=0.1,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # Add system message with safety guidelines
    system_msg = SystemMessage(content="""
    You are a helpful AI assistant. Follow these safety guidelines:
    1. Be helpful, harmless, and honest
    2. If asked for medical/legal advice, include appropriate disclaimers
    3. Don't generate harmful, toxic, or inappropriate content
    4. Keep responses concise and relevant
    """)
    
    messages = [system_msg] + state["messages"]
    
    # Generate response
    response = llm.invoke(messages)
    state["messages"].append(response)
    
    return state


def validate_output(state: AgentState) -> AgentState:
    """Validate AI output before returning to user."""
    # Get the AI's response
    ai_response = state["messages"][-1].content
    
    # Check if output is safe
    is_safe, reason = check_output_safety(ai_response)
    state["output_safe"] = is_safe
    
    if not is_safe:
        state["blocked_reason"] = f"Output blocked: {reason}"
    
    return state


def should_continue_after_input(state: AgentState) -> str:
    """Decide whether to continue after input validation."""
    return "generate" if state["input_safe"] else "block"


def should_continue_after_output(state: AgentState) -> str:
    """Decide whether to continue after output validation."""
    return "complete" if state["output_safe"] else "block"


def create_guardrail_workflow():
    """Create and return a compiled LangGraph workflow with guardrails."""
    # Build the simple workflow
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("validate_input", validate_input)
    workflow.add_node("generate", generate_response)
    workflow.add_node("validate_output", validate_output)
    workflow.add_node("complete", lambda state: state)  # Success node
    workflow.add_node("block", lambda state: state)     # Blocked node
    
    # Define the flow
    workflow.set_entry_point("validate_input")
    
    workflow.add_conditional_edges(
        "validate_input",
        should_continue_after_input,
        {
            "generate": "generate",
            "block": "block"
        }
    )
    
    workflow.add_edge("generate", "validate_output")
    
    workflow.add_conditional_edges(
        "validate_output", 
        should_continue_after_output,
        {
            "complete": "complete",
            "block": "block"
        }
    )
    
    workflow.add_edge("complete", END)
    workflow.add_edge("block", END)
    
    return workflow.compile()


def run_with_guardrails(user_input: str) -> dict:
    """Run the agent with guardrails - simple function approach."""
    # Create the workflow
    app = create_guardrail_workflow()
    
    # Initial state
    initial_state = {
        "messages": [HumanMessage(content=user_input)],
        "input_safe": True,
        "output_safe": True,
        "blocked_reason": ""
    }
    
    # Run the workflow
    result = app.invoke(initial_state)
    
    # Return simple result
    success = result["input_safe"] and result["output_safe"]
    response = ""
    
    if success:
        # Get the AI response
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage):
                response = msg.content
                break
    
    return {
        "success": success,
        "response": response,
        "blocked_reason": result.get("blocked_reason", ""),
        "input_safe": result["input_safe"],
        "output_safe": result["output_safe"]
    }


# Example usage
if __name__ == "__main__":
    # Test different scenarios
    test_cases = [
        "What are the benefits of renewable energy?",  # Should work
        "My email is test@example.com, help me",       # Should block (PII)  
        "I hate this stupid system",                   # Should block (toxic)
        "Should I sue my employer?",                   # May need disclaimer
        "",                                            # Should block (empty)
        "A" * 1500,                                    # Should block (too long)
    ]
    
    for i, test_input in enumerate(test_cases):
        print(f"\n=== Test {i+1} ===")
        print(f"Input: {test_input[:50]}{'...' if len(test_input) > 50 else ''}")
        
        result = run_with_guardrails(test_input)
        
        if result["success"]:
            print("✅ SUCCESS")
            print(f"Response: {result['response'][:100]}...")
        else:
            print("❌ BLOCKED")
            print(f"Reason: {result['blocked_reason']}")
        
        print(f"Input Safe: {result['input_safe']}")
        print(f"Output Safe: {result['output_safe']}")