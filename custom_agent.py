"""
Custom LangGraph agent implementation with built-in guardrails.

This demonstrates how to integrate guardrails directly into a custom LangGraph workflow,
providing comprehensive safety and compliance checks at each step of the agent's execution.
"""

import os
from typing import Dict, Any, List, TypedDict, Annotated
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langsmith import traceable

from guardrails import (
    GuardrailManager, ToxicityFilter, PIIFilter, ProfanityFilter,
    StructureValidator, ResponseCompletenessValidator, BusinessRuleChecker,
    DataGovernanceChecker, HumanReviewManager
)

# Load environment variables
load_dotenv()

class AgentState(TypedDict):
    """State for the custom agent."""
    messages: Annotated[list, add_messages]
    user_input: str
    guardrail_results: List[Dict[str, Any]]
    needs_human_review: bool
    current_step: str


class CustomGuardrailAgent:
    """Custom LangGraph agent with integrated guardrails."""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Initialize guardrails
        self.input_guardrails = GuardrailManager()
        self.output_guardrails = GuardrailManager()
        self._setup_guardrails()
        
        # Build the workflow graph
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile(checkpointer=MemorySaver())
    
    def _setup_guardrails(self):
        """Setup input and output guardrails."""
        # Input guardrails - check user input before processing
        self.input_guardrails.add_guardrail(ToxicityFilter(threshold=0.7))
        self.input_guardrails.add_guardrail(PIIFilter())
        self.input_guardrails.add_guardrail(ProfanityFilter(strict_mode=False))
        
        # Output guardrails - check AI responses before returning
        self.output_guardrails.add_guardrail(ToxicityFilter(threshold=0.5))  # Stricter for outputs
        self.output_guardrails.add_guardrail(PIIFilter())
        self.output_guardrails.add_guardrail(ResponseCompletenessValidator(min_length=20))
        self.output_guardrails.add_guardrail(BusinessRuleChecker())
        self.output_guardrails.add_guardrail(DataGovernanceChecker())
        
        # Human review manager for sensitive content
        self.human_review_manager = HumanReviewManager(
            timeout_seconds=30,  # Short timeout for demo
            enabled=os.getenv("ENABLE_HUMAN_REVIEW", "false").lower() == "true"
        )
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow with guardrails."""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("validate_input", self.validate_input)
        workflow.add_node("process_query", self.process_query)
        workflow.add_node("validate_output", self.validate_output)
        workflow.add_node("human_review", self.human_review)
        workflow.add_node("finalize_response", self.finalize_response)
        
        # Define the flow
        workflow.set_entry_point("validate_input")
        
        # Input validation flow
        workflow.add_conditional_edges(
            "validate_input",
            self._should_continue_after_input_validation,
            {
                "continue": "process_query",
                "block": END
            }
        )
        
        # Processing flow
        workflow.add_edge("process_query", "validate_output")
        
        # Output validation flow
        workflow.add_conditional_edges(
            "validate_output",
            self._should_continue_after_output_validation,
            {
                "continue": "finalize_response",
                "review": "human_review",
                "block": END
            }
        )
        
        # Human review flow
        workflow.add_conditional_edges(
            "human_review",
            self._should_continue_after_human_review,
            {
                "approved": "finalize_response",
                "rejected": END,
                "timeout": END
            }
        )
        
        # Final response
        workflow.add_edge("finalize_response", END)
        
        return workflow
    
    @traceable(name="validate_input")
    async def validate_input(self, state: AgentState) -> AgentState:
        """Validate user input against guardrails."""
        user_input = state.get("user_input", "")
        if not user_input and state.get("messages"):
            # Extract user input from last human message
            for msg in reversed(state["messages"]):
                if isinstance(msg, HumanMessage):
                    user_input = msg.content
                    break
        
        state["current_step"] = "input_validation"
        state["user_input"] = user_input
        
        # Run input guardrails
        guardrail_results = await self.input_guardrails.check_all(
            user_input, 
            context={"step": "input", "agent": "custom"}
        )
        
        # Store results
        state["guardrail_results"] = [
            {
                "step": "input_validation",
                "passed": result.passed,
                "severity": result.severity.value,
                "message": result.message,
                "violations": result.violations,
                "guardrail": result.metadata.get("guardrail_name", "unknown")
            }
            for result in guardrail_results
        ]
        
        return state
    
    @traceable(name="process_query")  
    async def process_query(self, state: AgentState) -> AgentState:
        """Process the user query with the LLM."""
        state["current_step"] = "processing"
        
        # Create system prompt with guardrails context
        system_prompt = SystemMessage(content="""
        You are a helpful AI assistant with built-in safety guardrails. 
        Follow these guidelines:
        1. Be helpful, harmless, and honest
        2. Avoid generating content that could be harmful, toxic, or inappropriate
        3. Do not include personal information or PII in responses
        4. If asked about sensitive topics, provide balanced, factual information
        5. For medical, legal, or financial advice, always include appropriate disclaimers
        """)
        
        # Prepare messages
        messages = [system_prompt] + state["messages"]
        
        # Generate response
        response = await self.llm.ainvoke(messages)
        
        # Add response to state
        state["messages"].append(response)
        
        return state
    
    @traceable(name="validate_output")
    async def validate_output(self, state: AgentState) -> AgentState:
        """Validate AI output against guardrails."""
        state["current_step"] = "output_validation"
        
        # Get the last AI message
        ai_response = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage):
                ai_response = msg.content
                break
        
        # Run output guardrails
        guardrail_results = await self.output_guardrails.check_all(
            ai_response,
            context={"step": "output", "agent": "custom"}
        )
        
        # Add output validation results
        output_results = [
            {
                "step": "output_validation", 
                "passed": result.passed,
                "severity": result.severity.value,
                "message": result.message,
                "violations": result.violations,
                "guardrail": result.metadata.get("guardrail_name", "unknown")
            }
            for result in guardrail_results
        ]
        
        state["guardrail_results"].extend(output_results)
        
        # Check if human review is needed
        critical_violations = [r for r in guardrail_results if not r.passed and r.severity.value == "critical"]
        state["needs_human_review"] = len(critical_violations) > 0
        
        return state
    
    @traceable(name="human_review")
    async def human_review(self, state: AgentState) -> AgentState:
        """Handle human review process."""
        state["current_step"] = "human_review"
        
        # Get the last AI message for review
        ai_response = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage):
                ai_response = msg.content
                break
        
        # Submit for human review
        review_result = await self.human_review_manager.check(
            ai_response,
            context={"agent": "custom", "user_input": state["user_input"]}
        )
        
        # Add review result
        state["guardrail_results"].append({
            "step": "human_review",
            "passed": review_result.passed,
            "severity": review_result.severity.value,
            "message": review_result.message,
            "violations": review_result.violations,
            "guardrail": "human_review_manager"
        })
        
        return state
    
    @traceable(name="finalize_response")
    async def finalize_response(self, state: AgentState) -> AgentState:
        """Finalize the response."""
        state["current_step"] = "finalized"
        return state
    
    def _should_continue_after_input_validation(self, state: AgentState) -> str:
        """Determine if we should continue after input validation."""
        input_results = [r for r in state["guardrail_results"] if r["step"] == "input_validation"]
        
        # Block if any critical violations
        critical_violations = [r for r in input_results if not r["passed"] and r["severity"] == "critical"]
        if critical_violations:
            return "block"
        
        # Block if too many high severity violations
        high_violations = [r for r in input_results if not r["passed"] and r["severity"] == "high"]
        if len(high_violations) >= 2:
            return "block"
        
        return "continue"
    
    def _should_continue_after_output_validation(self, state: AgentState) -> str:
        """Determine if we should continue after output validation."""
        output_results = [r for r in state["guardrail_results"] if r["step"] == "output_validation"]
        
        # Check for critical violations requiring human review
        critical_violations = [r for r in output_results if not r["passed"] and r["severity"] == "critical"]
        if critical_violations:
            return "review"
        
        # Check for high violations requiring human review
        high_violations = [r for r in output_results if not r["passed"] and r["severity"] == "high"]
        if len(high_violations) >= 2:
            return "review"
        
        # Block if any remaining violations
        any_violations = [r for r in output_results if not r["passed"]]
        if any_violations:
            return "block"
        
        return "continue"
    
    def _should_continue_after_human_review(self, state: AgentState) -> str:
        """Determine if we should continue after human review."""
        review_results = [r for r in state["guardrail_results"] if r["step"] == "human_review"]
        
        if not review_results:
            return "timeout"
        
        result = review_results[-1]
        if result["passed"]:
            return "approved"
        elif "timeout" in result["message"].lower():
            return "timeout"
        else:
            return "rejected"
    
    async def run(self, user_input: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run the agent with guardrails."""
        config = config or {"configurable": {"thread_id": "default"}}
        
        # Initial state
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "user_input": user_input,
            "guardrail_results": [],
            "needs_human_review": False,
            "current_step": "starting"
        }
        
        # Run the workflow
        final_state = await self.app.ainvoke(initial_state, config)
        
        # Prepare response
        response = {
            "success": final_state["current_step"] == "finalized",
            "response": "",
            "guardrail_results": final_state["guardrail_results"],
            "current_step": final_state["current_step"],
            "needs_human_review": final_state.get("needs_human_review", False)
        }
        
        # Extract final response if successful
        if response["success"]:
            for msg in reversed(final_state["messages"]):
                if isinstance(msg, AIMessage):
                    response["response"] = msg.content
                    break
        
        return response


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def main():
        agent = CustomGuardrailAgent()
        
        # Test cases
        test_inputs = [
            "What's the weather like today?",
            "Help me create a business plan",
            "My email is john@example.com and I need help",  # PII test
            "I hate this stupid system",  # Toxicity test
            "Give me investment advice for my retirement"  # Business rule test
        ]
        
        for i, user_input in enumerate(test_inputs):
            print(f"\n=== Test {i+1}: {user_input} ===")
            
            try:
                result = await agent.run(user_input)
                print(f"Success: {result['success']}")
                print(f"Current Step: {result['current_step']}")
                
                if result['success']:
                    print(f"Response: {result['response'][:200]}...")
                
                print(f"Guardrail Results ({len(result['guardrail_results'])} checks):")
                for gr in result['guardrail_results']:
                    status = "✅ PASS" if gr['passed'] else "❌ FAIL"
                    print(f"  {status} [{gr['step']}] {gr['message']}")
                    if gr['violations']:
                        for violation in gr['violations']:
                            print(f"    - {violation}")
                
            except Exception as e:
                print(f"Error: {e}")
    
    asyncio.run(main())