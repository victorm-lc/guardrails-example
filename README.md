# Simple LangGraph Guardrails Example

Learn the basics of adding safety guardrails to LangGraph applications! 

This is a **beginner-friendly** example that shows essential patterns without complex abstractions.

## Quick Start (2 minutes!)

### Simple Function Approach
```python
from simple_guardrails_agent import run_with_guardrails

result = run_with_guardrails("What are the benefits of renewable energy?")

if result["success"]:
    print("✅", result["response"]) 
else:
    print("❌ Blocked:", result["blocked_reason"])
```

### Prebuilt Agent with Hooks
```python
from prebuilt_with_guardrails import run_safe_agent

result = run_safe_agent("Search for information about climate change")

if result["success"]:
    print("✅", result["response"]) 
else:
    print("❌ Blocked:", result["blocked_reason"])
```

## What You'll Learn

- ✅ **Input validation** - Check user messages before processing
- ✅ **Output filtering** - Validate AI responses before returning  
- ✅ **LangGraph conditional edges** - Route based on safety checks
- ✅ **Pre/post-model hooks** - Add guardrails to existing agents
- ✅ **Simple safety patterns** - Toxicity, PII, length checks

## Two Approaches

### 1. Custom Workflow (`simple_guardrails_agent.py`)
- Build guardrails into a custom LangGraph workflow
- Full control over the agent flow
- Perfect for learning LangGraph concepts

### 2. Prebuilt Agent with Hooks (`prebuilt_with_guardrails.py`)  
- Add guardrails to existing ReAct agents
- Uses pre-model and post-model hooks
- Great for production applications

## Features

### Guardrail Types

- **Content Filtering**: Toxicity detection, PII filtering, profanity filtering
- **Output Validation**: Structure validation, format checking, completeness verification
- **Compliance Checking**: Business rules, industry-specific compliance (HIPAA, GDPR, etc.)
- **Human Review**: Human-in-the-loop workflows for sensitive content

### Integration Points

- **Input Validation**: Check user inputs before processing
- **Output Validation**: Validate AI responses before returning
- **Real-time Monitoring**: Track guardrail performance with LangSmith
- **Human Oversight**: Approval workflows for sensitive operations

## Project Structure

```
guardrails-example/
├── simple_guardrails_agent.py     # Custom workflow with guardrails
├── prebuilt_with_guardrails.py    # Prebuilt ReAct agent with hooks
├── examples/                       # Usage examples and demos
│   └── basic_usage.py             # Basic implementation examples
├── .env.example                   # Environment variables template
├── pyproject.toml                 # Dependencies and project config
└── README.md                      # This file
```

## Setup (2 minutes)

1. **Install dependencies**:
   ```bash
   pip install -e .
   ```

2. **Add your OpenAI API key**:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

3. **Run the examples**:
   ```bash
   # Custom workflow approach
   python simple_guardrails_agent.py
   
   # Prebuilt agent with hooks
   python prebuilt_with_guardrails.py
   ```

### Optional: LangSmith Tracing

```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=your_langsmith_api_key_here
```

## How It Works

### Custom Workflow Approach
The simple agent follows this flow:

```
User Input → Input Validation → LLM → Output Validation → Safe Response
     ↓               ↓              ↓            ↓
  "Hello"        ✅ Safe        "Hello!"    ✅ Safe      "Hello!"
"hate@me.com"   ❌ PII Block      —          —        "❌ Blocked: PII detected"
```

### Prebuilt Agent with Hooks
The prebuilt agent uses hooks around the existing ReAct pattern:

```
User Input → Pre-Model Hook → ReAct Agent → Post-Model Hook → Safe Response
     ↓            ↓               ↓              ↓
  "Search X"   ✅ Safe      "I searched..."   ✅ Safe     "I searched..."
"hate@me.com"  ❌ Block         —             —         "❌ Blocked: PII"
```

### Key Components

```python
# 1. Input validation
def check_input_safety(text: str) -> tuple[bool, str]:
    if not text: return False, "Empty input"
    if "hate" in text.lower(): return False, "Toxic content"
    if "@" in text: return False, "PII detected"
    return True, "Safe"

# 2. LangGraph workflow
workflow.add_conditional_edges(
    "validate_input",
    should_continue_after_input_validation,
    {"continue": "generate", "block": "block"}
)

# 3. Simple to understand!
```

## Customize Your Guardrails

Easily modify the simple agent for your needs:

```python
def check_input_safety(text: str) -> tuple[bool, str]:
    # Add your own rules here!
    
    if "bitcoin" in text.lower():
        return False, "No crypto discussion allowed"
    
    if len(text) > 500:  # Adjust length limit
        return False, "Please keep messages under 500 chars"
    
    return True, "Safe"
```

## Common Use Cases

1. **Customer Service Bot** - Block toxic messages, detect PII
2. **Content Moderation** - Filter inappropriate responses
3. **Compliance** - Ensure responses include required disclaimers  
4. **Data Protection** - Prevent leaking sensitive information

## Next Steps

Ready for more? Consider these production patterns:

- **Human-in-the-loop** workflows for sensitive content
- **Industry-specific** compliance rules (healthcare, finance, legal)  
- **Multi-layered** validation with severity levels
- **Performance optimization** with parallel processing
- **Monitoring** with LangSmith tracing

## Related Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangSmith Tracing](https://docs.smith.langchain.com/)
- [Guardrails AI](https://www.guardrailsai.com/)

---

**Perfect for learning LangGraph guardrails! Start simple, then explore advanced patterns.**
