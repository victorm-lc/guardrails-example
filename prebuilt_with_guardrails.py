"""
Prebuilt ReAct Agent with Guardrails Example

This example shows how to add guardrails to a prebuilt LangGraph ReAct agent
using pre-model and post-model hooks. This is perfect when you want to use
existing agent patterns but add safety checks.

Much simpler than building everything from scratch!
"""

import os
import re
from typing import Any, Dict
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent

load_dotenv()


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


def pre_model_hook(state: Dict[str, Any]) -> Dict[str, Any]:
    """Hook that runs BEFORE the model generates a response."""
    print("🔍 Pre-model guardrail check...")
    
    # Get the latest human message
    messages = state.get("messages", [])
    if not messages:
        return state
    
    # Find the last human message
    user_input = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_input = msg.content
            break
    
    if user_input:
        is_safe, reason = check_input_safety(user_input)
        if not is_safe:
            print(f"❌ Input blocked: {reason}")
            # Add a system message to block processing
            state["_guardrail_blocked"] = True
            state["_block_reason"] = f"Input blocked: {reason}"
            return state
    
    print("✅ Input passed safety check")
    return state


def post_model_hook(state: Dict[str, Any]) -> Dict[str, Any]:
    """Hook that runs AFTER the model generates a response."""
    print("🔍 Post-model guardrail check...")
    
    # Check if we already blocked in pre-hook
    if state.get("_guardrail_blocked", False):
        return state
    
    # Get the latest AI message
    messages = state.get("messages", [])
    if not messages:
        return state
    
    # Find the last AI message
    ai_response = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            ai_response = msg.content
            break
    
    if ai_response:
        is_safe, reason = check_output_safety(ai_response)
        if not is_safe:
            print(f"❌ Output blocked: {reason}")
            state["_guardrail_blocked"] = True
            state["_block_reason"] = f"Output blocked: {reason}"
            return state
    
    print("✅ Output passed safety check")
    return state


def create_safe_react_agent():
    """Create a ReAct agent with built-in guardrails using hooks."""
    # Create the LLM
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.1,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # Create some basic tools
    search_tool = DuckDuckGoSearchRun()
    tools = [search_tool]
    
    # Create the prebuilt ReAct agent
    agent = create_react_agent(llm, tools)
    
    return agent


def run_safe_agent(user_input: str) -> dict:
    """Run the ReAct agent with guardrails."""
    # Create the agent
    agent = create_safe_react_agent()
    
    # Initial state
    initial_state = {
        "messages": [HumanMessage(content=user_input)]
    }
    
    # Apply pre-model hook
    state_after_pre = pre_model_hook(initial_state)
    
    # Check if blocked by pre-hook
    if state_after_pre.get("_guardrail_blocked", False):
        return {
            "success": False,
            "response": "",
            "blocked_reason": state_after_pre.get("_block_reason", "Unknown block reason"),
            "blocked_stage": "pre_model"
        }
    
    try:
        # Run the agent
        result = agent.invoke(state_after_pre)
        
        # Apply post-model hook
        final_state = post_model_hook(result)
        
        # Check if blocked by post-hook
        if final_state.get("_guardrail_blocked", False):
            return {
                "success": False,
                "response": "",
                "blocked_reason": final_state.get("_block_reason", "Unknown block reason"),
                "blocked_stage": "post_model"
            }
        
        # Extract the final response
        messages = final_state.get("messages", [])
        response = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                response = msg.content
                break
        
        return {
            "success": True,
            "response": response,
            "blocked_reason": "",
            "blocked_stage": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "response": "",
            "blocked_reason": f"Error during execution: {str(e)}",
            "blocked_stage": "execution"
        }


# Example usage
if __name__ == "__main__":
    # Test different scenarios
    test_cases = [
        "What are the current weather trends?",          # Should work
        "My email is test@example.com, help me",        # Should block (PII)  
        "I hate this stupid system",                     # Should block (toxic)
        "Search for information about renewable energy", # Should work
        "",                                              # Should block (empty)
        "What's the best treatment for headaches?",      # May need disclaimer
    ]
    
    for i, test_input in enumerate(test_cases):
        print(f"\n{'='*50}")
        print(f"Test {i+1}: {test_input[:50]}{'...' if len(test_input) > 50 else ''}")
        print(f"{'='*50}")
        
        result = run_safe_agent(test_input)
        
        if result["success"]:
            print("✅ SUCCESS")
            print(f"Response: {result['response'][:200]}{'...' if len(result['response']) > 200 else ''}")
        else:
            print("❌ BLOCKED")
            print(f"Stage: {result['blocked_stage']}")
            print(f"Reason: {result['blocked_reason']}")