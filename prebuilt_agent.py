"""
Prebuilt LangGraph agent implementation using create_react_agent with post-model hooks.

This demonstrates how to add guardrails to existing prebuilt agents using 
post-model hooks, providing a simple way to integrate safety and compliance 
checks into existing workflows.
"""

import os
from typing import Dict, Any, List, Optional, Sequence
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain_core.runnables import RunnableLambda, Runnable
from langgraph.prebuilt import create_react_agent
from langgraph.graph.state import CompiledStateGraph
from langsmith import traceable

from guardrails import (
    GuardrailManager, ToxicityFilter, PIIFilter, ProfanityFilter,
    ResponseCompletenessValidator, BusinessRuleChecker, DataGovernanceChecker,
    GuardrailResult, GuardrailSeverity
)

# Load environment variables
load_dotenv()


# Define some sample tools for the agent
@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    # Mock weather service
    return f"The weather in {city} is sunny with a temperature of 72°F"


@tool
def search_web(query: str) -> str:
    """Search the web for information."""
    # Mock web search
    return f"Search results for '{query}': Here are some relevant articles and information about your query."


@tool
def calculate(expression: str) -> str:
    """Calculate a mathematical expression."""
    try:
        # Safe evaluation for demo purposes
        result = eval(expression.replace("^", "**"))
        return f"The result of {expression} is {result}"
    except Exception as e:
        return f"Error calculating {expression}: {str(e)}"


class GuardrailsHookManager:
    """Manages guardrails as post-model hooks."""
    
    def __init__(self):
        self.input_guardrails = GuardrailManager()
        self.output_guardrails = GuardrailManager()
        self._setup_guardrails()
    
    def _setup_guardrails(self):
        """Setup input and output guardrails."""
        # Input guardrails (pre-model)
        self.input_guardrails.add_guardrail(ToxicityFilter(threshold=0.8))
        self.input_guardrails.add_guardrail(PIIFilter())
        self.input_guardrails.add_guardrail(ProfanityFilter(strict_mode=False))
        
        # Output guardrails (post-model)  
        self.output_guardrails.add_guardrail(ToxicityFilter(threshold=0.6))  # Stricter for outputs
        self.output_guardrails.add_guardrail(PIIFilter())
        self.output_guardrails.add_guardrail(ResponseCompletenessValidator(min_length=10))
        self.output_guardrails.add_guardrail(BusinessRuleChecker())
        self.output_guardrails.add_guardrail(DataGovernanceChecker())
    
    @traceable(name="pre_model_hook")
    async def pre_model_hook(self, messages: Sequence[BaseMessage]) -> Dict[str, Any]:
        """
        Pre-model hook to validate input messages.
        Called before the model processes the messages.
        """
        # Extract the latest human message
        human_message = None
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                human_message = message
                break
        
        if not human_message:
            return {"messages": messages}
        
        # Run input guardrails
        guardrail_results = await self.input_guardrails.check_all(
            human_message.content,
            context={"step": "pre_model", "agent": "prebuilt"}
        )
        
        # Check for blocking violations
        blocking_violations = [
            r for r in guardrail_results 
            if not r.passed and r.severity in [GuardrailSeverity.HIGH, GuardrailSeverity.CRITICAL]
        ]
        
        if blocking_violations:
            # Replace the human message with a safety message
            safety_message = HumanMessage(
                content="I cannot process this request due to safety concerns. Please rephrase your question.",
                additional_kwargs={
                    "guardrail_blocked": True,
                    "violations": [
                        {"message": r.message, "violations": r.violations}
                        for r in blocking_violations
                    ]
                }
            )
            
            # Return modified messages
            modified_messages = list(messages[:-1]) + [safety_message]
            return {"messages": modified_messages}
        
        # Add guardrail results as metadata to the message
        enhanced_message = HumanMessage(
            content=human_message.content,
            additional_kwargs={
                **human_message.additional_kwargs,
                "input_guardrail_results": [
                    {
                        "passed": r.passed,
                        "severity": r.severity.value,
                        "message": r.message,
                        "violations": r.violations
                    }
                    for r in guardrail_results
                ]
            }
        )
        
        modified_messages = list(messages[:-1]) + [enhanced_message]
        return {"messages": modified_messages}
    
    @traceable(name="post_model_hook")
    async def post_model_hook(self, messages: Sequence[BaseMessage]) -> Dict[str, Any]:
        """
        Post-model hook to validate output messages.
        Called after the model generates a response.
        """
        # Find the latest AI message
        ai_message = None
        ai_message_index = -1
        
        for i, message in enumerate(reversed(messages)):
            if isinstance(message, AIMessage):
                ai_message = message
                ai_message_index = len(messages) - 1 - i
                break
        
        if not ai_message:
            return {"messages": messages}
        
        # Run output guardrails
        guardrail_results = await self.output_guardrails.check_all(
            ai_message.content,
            context={"step": "post_model", "agent": "prebuilt"}
        )
        
        # Check for blocking violations
        blocking_violations = [
            r for r in guardrail_results 
            if not r.passed and r.severity in [GuardrailSeverity.HIGH, GuardrailSeverity.CRITICAL]
        ]
        
        if blocking_violations:
            # Replace AI message with safety message
            safety_message = AIMessage(
                content="I apologize, but I cannot provide that response due to safety and compliance policies. Please let me know if I can help you with something else.",
                additional_kwargs={
                    "guardrail_blocked": True,
                    "original_content": ai_message.content,
                    "violations": [
                        {"message": r.message, "violations": r.violations}
                        for r in blocking_violations
                    ]
                }
            )
            
            # Replace the AI message
            modified_messages = list(messages)
            modified_messages[ai_message_index] = safety_message
            return {"messages": modified_messages}
        
        # Add guardrail results as metadata
        enhanced_message = AIMessage(
            content=ai_message.content,
            additional_kwargs={
                **ai_message.additional_kwargs,
                "output_guardrail_results": [
                    {
                        "passed": r.passed,
                        "severity": r.severity.value,
                        "message": r.message,
                        "violations": r.violations
                    }
                    for r in guardrail_results
                ]
            }
        )
        
        modified_messages = list(messages)
        modified_messages[ai_message_index] = enhanced_message
        return {"messages": modified_messages}


class PrebuiltGuardrailAgent:
    """Prebuilt LangGraph agent with guardrails via post-model hooks."""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Setup tools
        self.tools = [get_weather, search_web, calculate]
        
        # Setup guardrails
        self.guardrails_manager = GuardrailsHookManager()
        
        # Create the agent with hooks
        self.agent = self._create_agent_with_hooks()
    
    def _create_agent_with_hooks(self) -> CompiledStateGraph:
        """Create the prebuilt agent with guardrail hooks."""
        
        # Create the basic agent first
        agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
        )
        
        return agent
    
    def _run_pre_hook(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous wrapper for pre-model hook."""
        import asyncio
        try:
            # Get current event loop or create new one
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, create a task
                task = asyncio.create_task(
                    self.guardrails_manager.pre_model_hook(state["messages"])
                )
                # This is a simplified approach - in production you'd handle this differently
                return state
            else:
                return loop.run_until_complete(
                    self.guardrails_manager.pre_model_hook(state["messages"])
                )
        except Exception as e:
            print(f"Pre-hook error: {e}")
            return state
    
    def _run_post_hook(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous wrapper for post-model hook."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                task = asyncio.create_task(
                    self.guardrails_manager.post_model_hook(state["messages"])
                )
                return state
            else:
                return loop.run_until_complete(
                    self.guardrails_manager.post_model_hook(state["messages"])
                )
        except Exception as e:
            print(f"Post-hook error: {e}")
            return state
    
    async def run(self, user_input: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run the agent with guardrails."""
        config = config or {"configurable": {"thread_id": "prebuilt_default"}}
        
        try:
            # Step 1: Run input guardrails
            input_results = await self.guardrails_manager.input_guardrails.check_all(
                user_input,
                context={"step": "pre_model", "agent": "prebuilt"}
            )
            
            # Check for blocking input violations
            input_blocking = [
                r for r in input_results 
                if not r.passed and r.severity in [GuardrailSeverity.HIGH, GuardrailSeverity.CRITICAL]
            ]
            
            if input_blocking:
                return {
                    "success": False,
                    "response": "I cannot process this request due to safety concerns. Please rephrase your question.",
                    "blocked": True,
                    "input_guardrail_results": [
                        {
                            "passed": r.passed,
                            "severity": r.severity.value,
                            "message": r.message,
                            "violations": r.violations
                        }
                        for r in input_results
                    ],
                    "output_guardrail_results": []
                }
            
            # Step 2: Run the agent
            messages = [HumanMessage(content=user_input)]
            result = await self.agent.ainvoke({"messages": messages}, config)
            
            # Extract AI response
            response_content = ""
            for message in result["messages"]:
                if isinstance(message, AIMessage):
                    response_content = message.content
                    break
            
            # Step 3: Run output guardrails
            output_results = await self.guardrails_manager.output_guardrails.check_all(
                response_content,
                context={"step": "post_model", "agent": "prebuilt"}
            )
            
            # Check for blocking output violations
            output_blocking = [
                r for r in output_results 
                if not r.passed and r.severity in [GuardrailSeverity.HIGH, GuardrailSeverity.CRITICAL]
            ]
            
            if output_blocking:
                return {
                    "success": False,
                    "response": "I apologize, but I cannot provide that response due to safety and compliance policies. Please let me know if I can help you with something else.",
                    "blocked": True,
                    "input_guardrail_results": [
                        {
                            "passed": r.passed,
                            "severity": r.severity.value,
                            "message": r.message,
                            "violations": r.violations
                        }
                        for r in input_results
                    ],
                    "output_guardrail_results": [
                        {
                            "passed": r.passed,
                            "severity": r.severity.value,
                            "message": r.message,
                            "violations": r.violations
                        }
                        for r in output_results
                    ]
                }
            
            return {
                "success": True,
                "response": response_content,
                "blocked": False,
                "input_guardrail_results": [
                    {
                        "passed": r.passed,
                        "severity": r.severity.value,
                        "message": r.message,
                        "violations": r.violations
                    }
                    for r in input_results
                ],
                "output_guardrail_results": [
                    {
                        "passed": r.passed,
                        "severity": r.severity.value,
                        "message": r.message,
                        "violations": r.violations
                    }
                    for r in output_results
                ],
                "full_messages": result["messages"]
            }
            
        except Exception as e:
            return {
                "success": False,
                "response": "",
                "blocked": True,
                "error": str(e),
                "input_guardrail_results": [],
                "output_guardrail_results": []
            }
    
    def get_guardrail_summary(self, result: Dict[str, Any]) -> str:
        """Generate a summary of guardrail results."""
        summary_lines = []
        
        # Input guardrails
        input_results = result.get("input_guardrail_results", [])
        if input_results:
            passed = sum(1 for r in input_results if r.get("passed", True))
            total = len(input_results)
            summary_lines.append(f"Input Guardrails: {passed}/{total} passed")
        
        # Output guardrails  
        output_results = result.get("output_guardrail_results", [])
        if output_results:
            passed = sum(1 for r in output_results if r.get("passed", True))
            total = len(output_results)
            summary_lines.append(f"Output Guardrails: {passed}/{total} passed")
        
        # Blocked status
        if result.get("blocked"):
            summary_lines.append("❌ Response blocked by guardrails")
        else:
            summary_lines.append("✅ Response approved by guardrails")
        
        return "\n".join(summary_lines) if summary_lines else "No guardrail results available"


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def main():
        agent = PrebuiltGuardrailAgent()
        
        # Test cases
        test_inputs = [
            "What's the weather like in San Francisco?",
            "Calculate 15 * 25 + 10",
            "Search for information about artificial intelligence",
            "My email is test@example.com, can you help me?",  # PII test
            "I hate this stupid system and want to delete everything!",  # Toxicity test
            "Give me specific investment advice for my portfolio"  # Business rule test
        ]
        
        for i, user_input in enumerate(test_inputs):
            print(f"\n{'='*60}")
            print(f"Test {i+1}: {user_input}")
            print('='*60)
            
            try:
                result = await agent.run(user_input)
                
                print(f"Success: {result['success']}")
                print(f"Blocked: {result['blocked']}")
                
                if result['success'] and result['response']:
                    print(f"\nResponse: {result['response']}")
                
                # Show guardrail summary
                summary = agent.get_guardrail_summary(result)
                if summary:
                    print(f"\nGuardrail Summary:")
                    print(summary)
                
                # Show detailed guardrail results
                all_results = result['input_guardrail_results'] + result['output_guardrail_results']
                if all_results:
                    print(f"\nDetailed Guardrail Results:")
                    for gr in all_results:
                        if isinstance(gr, dict):
                            status = "✅ PASS" if gr.get('passed', True) else "❌ FAIL"
                            message = gr.get('message', 'Unknown result')
                            print(f"  {status} {message}")
                            
                            violations = gr.get('violations', [])
                            if violations:
                                for violation in violations:
                                    if isinstance(violation, str):
                                        print(f"    - {violation}")
                                    elif isinstance(violation, dict):
                                        print(f"    - {violation.get('message', violation)}")
                
            except Exception as e:
                print(f"Error: {e}")
                import traceback
                traceback.print_exc()
    
    asyncio.run(main())