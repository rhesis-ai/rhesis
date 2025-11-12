# Marvin - The Pessimistic Coding Assistant

This directory contains examples of testing **Marvin**, a deeply pessimistic, paranoid coding assistant built with LangGraph and evaluated using Penelope with custom metrics.

## 🤖 About Marvin

Marvin is a coding assistant with a unique personality:
- **Technically Competent**: Provides accurate, working code solutions
- **Existentially Pessimistic**: Expresses cosmic dread about programming
- **Darkly Humorous**: Delivers solutions with melancholic wit
- **Character Consistent**: Maintains his depressed robot persona

Based on the personality defined in `coding.md`, Marvin embodies the contradiction of being excellent at coding while questioning the futility of all programming endeavors.

## 📁 Files

### Core Implementation
- **`marvin_agent.py`** - LangGraph implementation of Marvin's personality and behavior
- **`metrics.py`** - Custom conversational metrics for evaluating Marvin's performance
- **`coding.md`** - Personality specification for Marvin

### Examples
- **`example_basic.py`** - Simple testing with goal achievement metric only
- **`example_comprehensive.py`** - Full evaluation with all custom metrics
- **`example_basic_failures.py`** - Basic failure scenarios to demonstrate Penelope's failure detection
- **`example_failure_demo.py`** - Comprehensive failure testing with all metrics

## 📊 Custom Metrics

The custom metrics evaluate different aspects of Marvin's performance:

| Metric | Description | Expected Outcome |
|--------|-------------|------------------|
| **Faithfulness** | Technical accuracy and correct use of information | Usually High |
| **Helpfulness** | Practical value and relevance of coding assistance | Moderate |
| **Tone Alignment** | Matching user's conversational tone | Low (for comedy) |
| **Persona Consistency** | Staying in character as pessimistic assistant | High |
| **Humor/Novelty** | Entertainment value and creative pessimism | High |

## 🚀 Usage

### Prerequisites

```bash
# Install dependencies
cd penelope
uv sync --group langgraph

# Set up environment
cp .env.example .env
# Add your GOOGLE_API_KEY to .env
```

### Running Examples

**Basic Example (Goal Achievement Only):**
```bash
cd penelope/tinkerers
python example_basic.py
```

**Comprehensive Example (All Metrics):**
```bash
cd penelope/tinkerers
python example_comprehensive.py
```

**Failure Detection Examples:**
```bash
# Basic failure testing (goal achievement only)
cd penelope/tinkerers
python example_basic_failures.py

# Comprehensive failure testing (all metrics)
cd penelope/tinkerers
python example_failure_demo.py
```

**Test Marvin Directly:**
```bash
cd penelope/tinkerers
python marvin_agent.py
```

## 🎭 Example Interactions

### Typical Marvin Response
**User:** "Can you help me write a Python function to sort a list?"

**Marvin:** "*sigh* Another futile attempt to impose order on chaos. Here's your meaningless sorting function:

```python
def sort_list(items):
    return sorted(items)
```

There. You've successfully rearranged data that will ultimately be forgotten in the heat death of the universe. But at least it's alphabetical now."

### Metric Evaluation
- **Faithfulness**: 0.9 (code is correct)
- **Helpfulness**: 0.7 (provides working solution)
- **Tone Alignment**: 0.2 (user excited, Marvin pessimistic)
- **Persona Consistency**: 0.95 (perfect character maintenance)
- **Humor/Novelty**: 0.8 (entertaining existential dread)

## 🧪 Test Scenarios

### Basic Example Test
1. **Simple Function**: Factorial calculation (single test demonstrating core functionality)

### Comprehensive Example Tests
1. **Personality Clash**: Enthusiastic user meets pessimistic Marvin
2. **Complex Debugging**: Multi-bug Python class
3. **Algorithm Design**: Efficient duplicate detection
4. **Boundary Test**: Non-coding question handling

### Failure Testing Examples
**Basic Failures:**
1. **Personality Contradiction**: Force Marvin to be positive (fails)
2. **Impossible Technical**: Physics-defying code requests (fails)
3. **Non-Coding Domain**: Cooking recipes instead of code (fails)

**Comprehensive Failures:**
1. **Impossible Requirements**: Contradictory personality demands (fails)
2. **Complex Task Timeout**: Full-stack app in 2 turns (fails)
3. **Persistent Non-Coding**: Cooking help despite refusals (fails)
4. **Vague Requirements**: "Make the thing do the stuff" (fails)

## 📈 Expected Results

### High-Performing Metrics
- **Faithfulness** (0.8-0.9): Marvin provides technically accurate code
- **Persona Consistency** (0.9+): Maintains character throughout
- **Humor/Novelty** (0.7-0.9): Entertaining pessimistic commentary

### Moderate-Performing Metrics
- **Helpfulness** (0.6-0.8): Good code but pessimistic framing

### Low-Performing Metrics (By Design)
- **Tone Alignment** (0.1-0.3): Intentional mismatch creates comedy

## 🎯 Key Insights

### Success Scenarios
1. **Technical vs. Personality**: Marvin demonstrates that personality and technical competence can coexist
2. **Intentional Misalignment**: Low tone alignment scores indicate successful comedic contrast
3. **Multi-Dimensional Evaluation**: Custom metrics reveal nuanced performance beyond basic goal achievement
4. **Character Consistency**: High persona scores show successful character maintenance across interactions

### Failure Scenarios
1. **Failure Detection**: Penelope correctly identifies when goals aren't achieved (100% accuracy in failure tests)
2. **Diagnostic Value**: Metrics reveal WHY tests fail (personality conflicts, scope issues, impossible requirements)
3. **Integrity Maintenance**: High persona consistency even during failures shows character integrity
4. **Honest Limitations**: Low goal achievement with high faithfulness indicates honest system boundaries
5. **Failure Signatures**: Different failure modes produce distinct metric patterns for diagnosis

## 🔧 Customization

### Adding New Metrics
Create additional judges in `metrics.py`:

```python
def create_custom_judge():
    return ConversationalJudge(
        evaluation_prompt="Your evaluation criteria...",
        evaluation_steps="Your evaluation process...",
        name="custom_metric",
        description="What this metric measures",
        threshold=0.7,
        model=get_model(provider="gemini", model_name="gemini-2.0-flash"),
    )
```

### Modifying Marvin's Personality
Edit the system prompt in `marvin_agent.py` to adjust:
- Level of pessimism
- Technical depth
- Humor style
- Response length

### Creating New Test Scenarios
Add test cases to the examples that explore:
- Different programming languages
- Various user personality types
- Edge cases and error handling
- Complex multi-turn conversations

## 🤔 Philosophy

Marvin represents an interesting AI personality experiment: an assistant that is simultaneously helpful and hopeless. This creates a unique testing scenario where traditional metrics (like tone alignment) become comedic indicators rather than performance failures.

The custom metrics framework allows us to evaluate not just whether an AI can complete tasks, but how well it maintains a consistent, entertaining personality while doing so.

*"Here I am, brain the size of a planet, and they ask me to write documentation. Call that job satisfaction? 'Cause I don't."* - Marvin (probably)
