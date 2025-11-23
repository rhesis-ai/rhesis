# SDK Endpoint Auto-Mapping

> **Smart, zero-config mapping system for SDK function integration**

## Overview

The SDK auto-mapping system automatically bridges the semantic gap between Rhesis's standardized input/output format and arbitrary SDK function signatures. It enables developers to register functions with minimal configuration while maintaining flexibility for complex cases.

## The Problem

Rhesis endpoints expect a standardized format for multi-turn conversations and test execution:

**Standard Input:**
```json
{
  "input": "user message",
  "session_id": "conversation-123",
  "context": ["document1", "document2"],
  "metadata": {"user_id": "abc"},
  "tool_calls": [...]
}
```

**Standard Output:**
```json
{
  "output": "response text",
  "session_id": "conversation-123",
  "context": [...],
  "metadata": {...},
  "tool_calls": [...]
}
```

However, SDK functions can have **any parameter names** and **any return structure**:

```python
# Example 1: Standard naming
def chat(input: str, session_id: str = None):
    return {"output": "...", "session_id": session_id}

# Example 2: Custom naming
def process_query(user_message: str, conv_id: str = None, docs: list = None):
    return {"result": {"text": "..."}, "conversation": conv_id}

# Example 3: Complex structure
def analyze(question: str, conversation_thread: str = None):
    return {"analysis": {"content": "..."}, "thread_id": conversation_thread}
```

**The Challenge:** How do we map between the standard format and these arbitrary signatures **automatically**, while allowing manual overrides when needed?

---

## The Solution: 4-Tier Priority System

The mapping system uses a cascading priority approach:

```
┌─────────────────────────────────────────────────────┐
│  1. SDK Manual Mappings (from @collaborate)        │ ← Highest Priority
│     Developer explicitly defines mappings           │
├─────────────────────────────────────────────────────┤
│  2. Existing DB Mappings (preserved on reconnect)  │
│     Manual edits made via UI are preserved          │
├─────────────────────────────────────────────────────┤
│  3. Auto-Mapping (pattern-based heuristics)        │
│     Smart pattern matching (>= 0.7 confidence)      │
├─────────────────────────────────────────────────────┤
│  4. LLM Fallback (when auto-mapping fails)         │
│     GPT-4 generates mappings (< 0.7 confidence)     │
└─────────────────────────────────────────────────────┘
```

### Priority 1: SDK Manual Mappings

Developer provides explicit mappings in the `@collaborate` decorator:

```python
from rhesis.sdk import collaborate

@collaborate(
    request_template={
        "user_query": "{{ input }}",
        "conv_id": "{{ session_id }}",
        "docs": "{{ context }}"
    },
    response_mappings={
        "output": "{{ jsonpath('$.result.text') }}",
        "session_id": "$.conv_id",
        "context": "$.sources"
    }
)
def chat(user_query: str, conv_id: str = None, docs: list = None):
    return {
        "result": {"text": "Hello!"},
        "conv_id": conv_id,
        "sources": docs
    }
```

**When to use:** Custom naming, nested structures, or domain-specific requirements.

### Priority 2: Existing DB Mappings

If an endpoint already has mappings in the database (from previous auto-mapping or manual configuration via UI), those mappings are preserved on SDK reconnection. This prevents overwriting user customizations.

**Behavior:** Skip mapping generation entirely, use existing configuration.

### Priority 3: Auto-Mapping (Pattern-Based)

Uses sophisticated semantic pattern matching to detect standard fields:

**Input Pattern Matching:**
- Exact: `input`, `query`, `prompt`, `message`, `text`
- Compound: `user_input`, `user_query`, `chat_message`, etc.
- Partial: `question`, `ask`, `request`, `instruction`

**Session Pattern Matching:**
- Exact: `session_id`, `conversation_id`, `thread_id`, `chat_id`
- Compound: `conv_id`, `session_key`, `chat_session_id`, etc.
- Partial: `conv`, `convo`, `sess`

**Confidence Scoring:**
```python
confidence = (
    0.5 if "input" matched +       # Critical field
    0.2 if "session_id" matched +  # Important for multi-turn
    0.1 if "context" matched +     # Optional but valuable
    0.1 if "metadata" matched +    # Optional
    0.1 if "tool_calls" matched    # Optional
)
```

**Threshold:** Auto-mapping succeeds if confidence >= 0.7 (e.g., input + session_id matched).

**Example Auto-Mapping:**
```python
# Function signature
def chat(input: str, session_id: str = None, context: list = None):
    return {"output": "...", "session_id": session_id}

# Generated mappings (confidence: 0.8)
request_template = {
    "input": "{{ input }}",
    "session_id": "{{ session_id }}",
    "context": "{{ context }}"
}
response_mappings = {
    "output": "{{ response or result or output or content }}",
    "session_id": "{{ session_id or conversation_id or conv_id }}",
    # ... fallback patterns for flexibility
}
```

### Priority 4: LLM Fallback

When auto-mapping confidence is below 0.7, the system uses the user's configured generation model (e.g., GPT-4) to intelligently generate mappings.

**LLM Prompt Structure:**
- Function signature with parameter types
- Standard Rhesis input/output format
- Mapping format requirements (Jinja2 for input, JSONPath/Jinja2 for output)
- Confidence scoring guidance

**Structured Output:** Uses Pydantic schema to ensure valid, parseable mappings.

**Example LLM Generation:**
```python
# Complex function signature
def analyze_query(user_message: str, conversation_thread: str = None):
    return {
        "analysis": {"summary": "...", "confidence": 0.9},
        "thread": conversation_thread
    }

# LLM generates:
request_template = {
    "user_message": "{{ input }}",
    "conversation_thread": "{{ session_id }}"
}
response_mappings = {
    "output": "{{ jsonpath('$.analysis.summary') }}",
    "session_id": "$.thread"
}
# confidence: 0.85, reasoning: "Mapped user_message to input..."
```

---

## Usage Examples

### Zero-Config (Most Common)

For functions with standard naming, no configuration needed:

```python
from rhesis.sdk import collaborate

@collaborate()  # That's it!
def chat(input: str, session_id: str = None):
    return {"output": f"Echo: {input}", "session_id": session_id}
```

**Result:** Auto-mapped with 0.7 confidence (input + session_id).

### Partial Override

Mix auto-mapping with custom hints:

```python
@collaborate(
    # Only override what's different, rest is auto-mapped
    request_template={
        "user_query": "{{ input }}",  # Custom parameter name
    }
)
def chat(user_query: str, session_id: str = None):
    return {"output": "...", "session_id": session_id}
```

### Full Custom Mapping

Complete control for complex scenarios:

```python
@collaborate(
    request_template={
        "q": "{{ input }}",
        "thread": "{{ session_id }}",
        "docs": "{{ context }}",
        "meta": "{{ metadata }}"
    },
    response_mappings={
        "output": "{{ jsonpath('$.result.response.text') }}",
        "session_id": "$.thread_info.id",
        "context": "$.retrieved_docs",
        "metadata": "$.metrics"
    }
)
def complex_chat(q: str, thread: str = None, docs: list = None, meta: dict = None):
    return {
        "result": {"response": {"text": "..."}},
        "thread_info": {"id": thread},
        "retrieved_docs": docs,
        "metrics": {"tokens": 100}
    }
```

---

## Architecture

### Module Structure

```
mapping/
├── patterns.py          # Pattern definitions and field configs
├── auto_mapper.py       # Heuristic-based auto-detection
├── llm_mapper.py        # LLM-based mapping generation
├── mapper_service.py    # Orchestration (4-tier priority)
├── validator.py         # Synchronous test validation
└── mapping_generation.jinja  # LLM prompt template
```

### Key Components

#### `patterns.py`

**Configuration-Driven Design:**
```python
@dataclass
class FieldConfig:
    name: str              # "input", "session_id", etc.
    pattern_type: str      # Pattern lookup key
    template_var: str      # Jinja2 template variable
    confidence_weight: float  # Weight for confidence calculation
    is_required: bool = False

STANDARD_FIELDS = [
    FieldConfig("input", "input", "{{ input }}", 0.5, True),
    FieldConfig("session_id", "session", "{{ session_id }}", 0.2),
    # ... add new fields here
]
```

**Adding New Fields:** Just add patterns and a `FieldConfig` entry. No code changes needed in `auto_mapper.py`.

#### `auto_mapper.py`

**Data-Driven Mapping:**
```python
# Automatically iterates through STANDARD_FIELDS
for field_config in MappingPatterns.STANDARD_FIELDS:
    match = self._find_best_match(param_names, field_config.pattern_type)
    if match:
        request_template[param_name] = field_config.template_var
        matched_fields.append(field_config.name)
```

#### `mapper_service.py`

**Returns Pydantic Model:**
```python
class MappingResult(BaseModel):
    request_template: Dict[str, str]
    response_mappings: Dict[str, str]
    source: Literal["sdk_manual", "existing_db", "auto_mapped", "llm_generated"]
    confidence: float  # 0.0-1.0
    should_update: bool
    reasoning: str
```

#### `validator.py`

**Synchronous Test Execution:**
- Sends test request to SDK via WebSocket
- Validates mappings work correctly
- Sets endpoint status to "Active" (success) or "Error" (failure)

---

## Integration with Endpoint Sync

When an SDK connects/reconnects, the mapping system is automatically invoked:

```python
# In endpoint.py - sync_sdk_endpoints()

# 1. Generate/use mappings
mapping_result = mapper_service.generate_or_use_existing(
    db=db,
    user=user,
    endpoint=endpoint,
    sdk_metadata=func_data.get("metadata", {}),
    function_data=func_data,
)

# 2. Update endpoint if needed
if mapping_result.should_update:
    endpoint.request_body_template = mapping_result.request_template
    endpoint.response_mappings = mapping_result.response_mappings
    
    # Store metadata for transparency
    endpoint.endpoint_metadata["mapping_info"] = {
        "source": mapping_result.source,
        "confidence": mapping_result.confidence,
        "reasoning": mapping_result.reasoning,
        "generated_at": datetime.utcnow().isoformat(),
    }

# 3. Validate mappings synchronously
validation_result = await validator.validate_mappings(...)
if validation_result["success"]:
    endpoint.status = "Active"
else:
    endpoint.status = "Error"
```

---

## Extending the System

### Adding a New Standard Field

1. **Add patterns to `patterns.py`:**
```python
USER_ID_EXACT = ["user_id", "uid", "user"]
USER_ID_COMPOUND = ["user_identifier", "account_id"]
USER_ID_PARTIAL = ["usr"]
```

2. **Add field config:**
```python
FieldConfig(
    name="user_id",
    pattern_type="user_id",
    template_var="{{ user_id }}",
    confidence_weight=0.1,
    is_required=False,
)
```

3. **Update pattern mapping:**
```python
"user_id": (cls.USER_ID_EXACT, cls.USER_ID_COMPOUND, cls.USER_ID_PARTIAL)
```

That's it! The field will be automatically mapped by `auto_mapper.py`.

### Adjusting Confidence Weights

Modify weights in `STANDARD_FIELDS` to change priority:

```python
# Make session_id more important
FieldConfig("session_id", "session", "{{ session_id }}", 0.3),  # was 0.2
```

### Changing LLM Threshold

Modify the confidence check in `mapper_service.py`:

```python
if auto_result["confidence"] >= 0.6:  # was 0.7, now more aggressive LLM fallback
```

---

## Best Practices

### For SDK Developers

1. **Use standard naming when possible** → Zero config, instant auto-mapping
2. **Provide manual mappings for complex cases** → Explicit is better than implicit
3. **Test your functions** → Validation catches mapping issues early
4. **Document your function signatures** → Helps LLM generate better mappings

### For Platform Developers

1. **Add patterns conservatively** → Avoid false positives
2. **Monitor auto-mapping confidence** → Identify patterns that need improvement
3. **Review LLM-generated mappings** → Fine-tune prompts based on results
4. **Preserve user edits** → Priority 2 ensures manual changes aren't lost

---

## Monitoring & Debugging

### Mapping Metadata

Every endpoint stores mapping metadata for transparency:

```json
{
  "mapping_info": {
    "source": "auto_mapped",
    "confidence": 0.8,
    "reasoning": "Auto-detected from function signature. Matched: ['input', 'session_id', 'context']",
    "generated_at": "2025-11-23T10:30:00Z"
  }
}
```

### Logs

The system logs detailed information at each step:

```
[chat] Generating/validating mappings...
[chat] Attempting auto-mapping
Matched input → input (confidence: 1.00)
Matched session_id → session_id (confidence: 1.00)
Matched context → context (confidence: 1.00)
[chat] Auto-mapping successful (confidence: 0.80)
[chat] Updated mappings (source: auto_mapped, confidence: 0.80)
[chat] Validating mappings...
[chat] ✓ Validation passed
```

### Endpoint Status

- **Active:** Mappings validated successfully
- **Error:** Validation failed (endpoint created but non-functional)
- **Inactive:** Function no longer registered

---

## Summary

The SDK auto-mapping system provides:

✅ **Zero-config for 80% of cases** - Standard naming works out of the box  
✅ **Smart fallbacks** - Pattern matching → LLM → Manual override  
✅ **Preservation of edits** - Database mappings never overwritten  
✅ **Full transparency** - Source, confidence, and reasoning tracked  
✅ **Type safety** - Pydantic models ensure correctness  
✅ **Extensibility** - Add fields without touching core logic  
✅ **Validation** - Test execution before marking as active  

**Result:** Developers can register SDK functions with minimal friction while maintaining flexibility for complex scenarios.

